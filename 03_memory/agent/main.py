"""
AgentCore Runtime Entrypoint for the memory-enabled Cost Estimator Agent

Differences from the plain CostEstimatorAgent entrypoint:
- session_id and actor_id are taken from the Runtime invocation context and
  passed down, so each conversation gets its own AgentCore Memory session
- the raw user prompt is forwarded as-is so that what gets written to memory
  reads like a natural conversation rather than a wrapped template
"""

import os
import traceback
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from cost_estimator_agent import AWSCostEstimatorAgent

app = BedrockAgentCoreApp()
log = app.logger

# --- Constants ---
REGION = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION', 'us-west-2')
DEFAULT_ACTOR_ID = "default-user"

# --- Singleton ---
_agent = None


def get_or_create_agent() -> AWSCostEstimatorAgent:
    """Get or create the cost estimation agent (singleton).

    AWSCostEstimatorAgent is the facade that owns model, tools, and MCP
    client. Creating it once avoids repeated MCP connection and model
    initialization. It hands out one Strands Agent per (session, actor).
    """
    global _agent
    if _agent is None:
        _agent = AWSCostEstimatorAgent(region=REGION)
    return _agent


def _resolve_actor_id(payload: dict, context) -> str:
    """Resolve the actor (user) that owns the long-term memory namespace.

    The CLI's ``--user-id`` flag travels as the
    ``X-Amzn-Bedrock-AgentCore-Runtime-User-Id`` header, which the Runtime does
    not forward to agent code, so ``context.user_id`` is not populated today.
    We therefore also accept ``actor_id`` in the payload, which lets callers
    (the AWS console Test Endpoint, boto3, a web front end) scope memory per
    user. ``context.user_id`` is checked first so this keeps working if the SDK
    starts exposing it.
    """
    return (
        getattr(context, "user_id", None)
        or payload.get("actor_id")
        or DEFAULT_ACTOR_ID
    )


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint with streaming response and memory.

    Implements delta-based streaming following Amazon Bedrock best practices.
    """
    log.info("Invoking Cost Estimator Agent with Memory...")

    prompt = payload.get("prompt")
    session_id = getattr(context, "session_id", None)
    actor_id = _resolve_actor_id(payload, context)

    log.info(f"session_id={session_id} actor_id={actor_id}")

    agent = get_or_create_agent()

    try:
        previous_output = ""

        async for event in agent.stream(prompt, session_id=session_id, actor_id=actor_id):
            if "data" in event:
                current_chunk = str(event["data"])

                # Handle delta calculation following Bedrock best practices
                if current_chunk.startswith(previous_output):
                    delta_content = current_chunk[len(previous_output):]
                    if delta_content:
                        previous_output = current_chunk
                        yield delta_content
                else:
                    previous_output = current_chunk
                    yield current_chunk

    except Exception as e:
        log.error(f"❌ Streaming cost estimation failed: {e}")
        yield f"❌ Streaming cost estimation failed: {e}\n\nStacktrace:\n{traceback.format_exc()}"


if __name__ == "__main__":
    app.run()
