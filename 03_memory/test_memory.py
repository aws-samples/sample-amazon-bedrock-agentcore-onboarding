#!/usr/bin/env python3
"""Verify AgentCore Memory behaviour on a deployed agent.

Lab 3 layers agent/ over the base CostEstimatorAgent to add memory. This
script exercises the three behaviours the lab teaches:

1. Short-term memory  — two turns in the SAME session; the agent recalls the
   previous estimate without calling any tool.
2. Long-term memory   — a NEW session with the SAME actor; preferences stated
   earlier are carried over via the USER_PREFERENCE / SEMANTIC strategies.
3. Actor isolation     — a DIFFERENT actor sees none of that, because
   namespaceTemplates scope long-term memory by {actorId}.

Long-term extraction is asynchronous, so phase 2 waits before asking.

Usage:
    # Get both values from `agentcore status` in your project directory
    uv run python test_memory.py \\
        --agent-arn <runtime-arn> \\
        --memory-id <memory-id>

    # Run a single phase
    uv run python test_memory.py --agent-arn ... --memory-id ... --phase short
"""

import argparse
import json
import time
import uuid

import boto3

DEFAULT_ACTOR_ID = "default-user"
OTHER_ACTOR_ID = "alice"


def invoke(client, agent_arn: str, prompt: str, session_id: str, actor_id: str) -> str:
    """Invoke the agent and return the concatenated response text.

    actor_id is passed in the payload because the Runtime does not forward the
    X-Amzn-Bedrock-AgentCore-Runtime-User-Id header to agent code, so
    `agentcore invoke --user-id` never reaches context.user_id.
    """
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        contentType="application/json",
        payload=json.dumps({"prompt": prompt, "actor_id": actor_id}).encode(),
        qualifier="DEFAULT",
    )

    chunks = []
    for line in response["response"].iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if not decoded.startswith("data: "):
            continue
        chunk = json.loads(decoded[len("data: "):])
        chunks.append(chunk)
        print(chunk, end="", flush=True)
    print()
    return "".join(chunks)


# --- Default prompts -------------------------------------------------------
# The agent answers in the language of the prompt. Override these to run the
# verification in another language, e.g. --prompt-estimate "..." in Japanese.
DEFAULT_ESTIMATE_PROMPT = (
    "Estimate the cost of one EC2 t3.nano in us-west-2. "
    "I always want the smallest configuration to keep costs down."
)
DEFAULT_RECALL_PROMPT = (
    "Which instance did you just estimate, and what was the monthly cost?"
)
DEFAULT_PREFERENCE_PROMPT = (
    "I prefer Graviton (ARM) instances and I always use us-west-2. "
    "I want to stay within a budget of 10 USD per month. "
    "Estimate a t4g.nano under those conditions."
)
DEFAULT_LONG_TERM_PROMPT = (
    "Following my preferences, propose one EC2 configuration for a small test "
    "environment and estimate its cost. Choose the region and instance type "
    "based on what you know I prefer."
)
DEFAULT_ISOLATION_PROMPT = (
    "Given my budget and preferences, tell me just the instance type you "
    "recommend, in one phrase."
)


def header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def phase_short_term(
    client,
    agent_arn: str,
    actor_id: str,
    estimate_prompt: str = DEFAULT_ESTIMATE_PROMPT,
    recall_prompt: str = DEFAULT_RECALL_PROMPT,
    preference_prompt: str = DEFAULT_PREFERENCE_PROMPT,
) -> None:
    """Two turns in the same session — short-term memory (ListEvents)."""
    session_id = str(uuid.uuid4())

    header(f"[1] Short-term — ask for an estimate (session={session_id[:8]}...)")
    invoke(client, agent_arn, estimate_prompt, session_id, actor_id)

    header("[2] Short-term — ask about the previous estimate in the same session")
    invoke(client, agent_arn, recall_prompt, session_id, actor_id)

    header("[3] Long-term material — state preferences (same session)")
    invoke(client, agent_arn, preference_prompt, session_id, actor_id)


def show_memory_records(memory_id: str, actor_id: str, region: str, query: str) -> int:
    """Print long-term memory records for the actor. Returns the record count."""
    client = boto3.client("bedrock-agentcore", region_name=region)
    total = 0
    for namespace in (f"/users/{actor_id}/preferences", f"/users/{actor_id}/facts"):
        try:
            response = client.retrieve_memory_records(
                memoryId=memory_id,
                namespace=namespace,
                searchCriteria={"searchQuery": query, "topK": 3},
            )
        except Exception as e:  # noqa: BLE001 — surface the reason and continue
            print(f"  {namespace}: ⚠️ {e}")
            continue

        records = response.get("memoryRecordSummaries", [])
        total += len(records)
        print(f"  {namespace}: {len(records)} records")
        for record in records:
            score = record.get("score", 0.0)
            text = record.get("content", {}).get("text", "").replace("\n", " ")
            print(f"    - score={score:.3f} {text[:120]}")
    return total


def phase_long_term(
    client,
    agent_arn: str,
    memory_id: str,
    actor_id: str,
    region: str,
    wait: int,
    long_term_prompt: str = DEFAULT_LONG_TERM_PROMPT,
) -> None:
    """A new session with the same actor — long-term memory."""
    query = "user preferences for AWS instance type, region and budget"

    header(f"[4] Wait for long-term extraction (up to {wait}s)")
    elapsed = 0
    interval = 30
    while True:
        print(f"-- {elapsed}s")
        if show_memory_records(memory_id, actor_id, region, query) > 0:
            break
        if elapsed >= wait:
            print("⚠️ Long-term memory has not been extracted yet. Wait and re-run.")
            break
        time.sleep(min(interval, wait - elapsed))
        elapsed += interval

    header("[5] Long-term — ask a preference-dependent question in a new session")
    print("(If Graviton and the 10 USD budget show up, long-term memory is working)\n")
    invoke(client, agent_arn, long_term_prompt, str(uuid.uuid4()), actor_id)


def phase_isolation(
    client,
    agent_arn: str,
    other_actor_id: str,
    isolation_prompt: str = DEFAULT_ISOLATION_PROMPT,
) -> None:
    """A different actor — namespace isolation."""
    header(f"[6] Actor isolation — same question as actor_id={other_actor_id}")
    print("(If the agent asks back instead of assuming, isolation works)\n")
    invoke(client, agent_arn, isolation_prompt, str(uuid.uuid4()), other_actor_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify AgentCore Memory behaviour on a deployed agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent-arn", required=True, help="Runtime ARN (see `agentcore status`)")
    parser.add_argument("--memory-id", required=True, help="Memory ID (see `agentcore status`)")
    parser.add_argument("--actor-id", default=DEFAULT_ACTOR_ID, help="Actor that owns the memory")
    parser.add_argument("--other-actor-id", default=OTHER_ACTOR_ID, help="Actor used for isolation")
    parser.add_argument("--region", default=None, help="AWS region (defaults to the profile)")
    parser.add_argument(
        "--wait",
        type=int,
        default=300,
        help="Seconds to wait for asynchronous long-term extraction (default: 300)",
    )
    parser.add_argument(
        "--phase",
        choices=["all", "short", "long", "isolation"],
        default="all",
        help="Which phase to run (default: all)",
    )
    prompts = parser.add_argument_group(
        "prompts",
        "The agent answers in the language of the prompt. Override these to run the "
        "verification in another language.",
    )
    prompts.add_argument(
        "--prompt-estimate",
        default=DEFAULT_ESTIMATE_PROMPT,
        help="[1] Ask for an estimate and state a general preference",
    )
    prompts.add_argument(
        "--prompt-recall",
        default=DEFAULT_RECALL_PROMPT,
        help="[2] Ask about the previous estimate in the same session",
    )
    prompts.add_argument(
        "--prompt-preference",
        default=DEFAULT_PREFERENCE_PROMPT,
        help="[3] State the preferences that long-term memory should extract",
    )
    prompts.add_argument(
        "--prompt-long-term",
        default=DEFAULT_LONG_TERM_PROMPT,
        help="[5] Preference-dependent question asked in a new session",
    )
    prompts.add_argument(
        "--prompt-isolation",
        default=DEFAULT_ISOLATION_PROMPT,
        help="[6] Same question asked as a different actor",
    )
    args = parser.parse_args()

    region = args.region or boto3.Session().region_name
    client = boto3.client("bedrock-agentcore", region_name=region)

    if args.phase in ("all", "short"):
        phase_short_term(
            client,
            args.agent_arn,
            args.actor_id,
            args.prompt_estimate,
            args.prompt_recall,
            args.prompt_preference,
        )
    if args.phase in ("all", "long"):
        phase_long_term(
            client,
            args.agent_arn,
            args.memory_id,
            args.actor_id,
            region,
            args.wait,
            args.prompt_long_term,
        )
    if args.phase in ("all", "isolation"):
        phase_isolation(
            client, args.agent_arn, args.other_actor_id, args.prompt_isolation
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
