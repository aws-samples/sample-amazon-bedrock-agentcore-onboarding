#!/usr/bin/env python3
"""Invoke a deployed AgentCore Runtime agent with boto3.

Lab 2 deploys the base CostEstimatorAgent as-is, so this directory holds no
agent code — only this client script. It demonstrates the
InvokeAgentRuntime API, which is what you would call from an application
(a web form, a batch job, another service).

The agent entrypoint streams text with `yield`, so the Runtime returns
Server-Sent Events (text/event-stream) rather than a single JSON document.
Each line looks like `data: "<json-encoded chunk>"`.

Usage:
    # Get the runtime ARN from `agentcore status` in your project directory
    uv run python invoke_agent.py --agent-arn <runtime-arn> \\
        --prompt "Estimate the monthly cost of storing 10GB in S3 in us-west-2."

    # Two turns in the same session to see conversation continuity
    uv run python invoke_agent.py --agent-arn <runtime-arn> --demo-session
"""

import argparse
import json
import uuid

import boto3

# The agent answers in the language of the prompt. Override to run in another language.
DEFAULT_PROMPT = "Estimate the monthly cost of storing 10GB in S3 in us-west-2."
DEFAULT_DEMO_FIRST_PROMPT = "[quick] What is the monthly cost of one EC2 t3.nano?"
DEFAULT_DEMO_FOLLOWUP_PROMPT = (
    "Which instance type did I just ask about? Answer in one phrase."
)


def invoke(client, agent_arn: str, prompt: str, session_id: str, quiet: bool = False) -> str:
    """Invoke the agent once and return the concatenated response text."""
    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        contentType="application/json",
        payload=json.dumps({"prompt": prompt}).encode(),
        qualifier="DEFAULT",
    )

    if not quiet:
        print(f"statusCode: {response['statusCode']}")
        print(f"sessionId : {response['runtimeSessionId']}")
        print("-" * 40)

    chunks = []
    for line in response["response"].iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        if not decoded.startswith("data: "):
            continue
        chunk = json.loads(decoded[len("data: "):])
        chunks.append(chunk)
        if not quiet:
            print(chunk, end="", flush=True)

    if not quiet:
        print()
    return "".join(chunks)


def demo_session(
    client,
    agent_arn: str,
    first_prompt: str = DEFAULT_DEMO_FIRST_PROMPT,
    followup_prompt: str = DEFAULT_DEMO_FOLLOWUP_PROMPT,
) -> None:
    """Show that a session keeps context and a new session does not."""
    # runtimeSessionId must be at least 33 characters
    session_id = str(uuid.uuid4())

    print("=" * 60)
    print(f"[1] session={session_id}")
    print("=" * 60)
    invoke(client, agent_arn, first_prompt, session_id)

    print()
    print("=" * 60)
    print("[2] same session — should recall t3.nano")
    print("=" * 60)
    invoke(client, agent_arn, followup_prompt, session_id)

    print()
    print("=" * 60)
    print("[3] new session — should NOT recall")
    print("=" * 60)
    invoke(client, agent_arn, followup_prompt, str(uuid.uuid4()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Invoke a deployed AgentCore Runtime agent with boto3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent-arn",
        required=True,
        help="Runtime ARN (see `agentcore status`)",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Prompt to send")
    parser.add_argument(
        "--session-id",
        help="Runtime session ID (33+ characters). Defaults to a fresh UUID",
    )
    parser.add_argument("--region", default=None, help="AWS region (defaults to the profile)")
    parser.add_argument(
        "--demo-first-prompt",
        default=DEFAULT_DEMO_FIRST_PROMPT,
        help="First prompt of --demo-session",
    )
    parser.add_argument(
        "--demo-followup-prompt",
        default=DEFAULT_DEMO_FOLLOWUP_PROMPT,
        help="Follow-up prompt of --demo-session, reused for the new session",
    )
    parser.add_argument(
        "--demo-session",
        action="store_true",
        help="Run a 3-call demo showing session-scoped conversation continuity",
    )
    args = parser.parse_args()

    region = args.region or boto3.Session().region_name
    client = boto3.client("bedrock-agentcore", region_name=region)

    if args.demo_session:
        demo_session(
            client, args.agent_arn, args.demo_first_prompt, args.demo_followup_prompt
        )
    else:
        invoke(client, args.agent_arn, args.prompt, args.session_id or str(uuid.uuid4()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
