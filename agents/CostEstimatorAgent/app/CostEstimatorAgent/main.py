"""
AgentCore Runtime Entrypoint for Cost Estimator Agent

Follows the AgentCore CLI scaffold pattern:
- get_or_create_agent() returns AWSCostEstimatorAgent singleton
- AWSCostEstimatorAgent encapsulates all tool/model/MCP construction (facade)
- @app.entrypoint handles streaming with delta deduplication
"""

import os
import traceback
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from cost_estimator_agent import AWSCostEstimatorAgent
from config import COST_ESTIMATION_PROMPT

app = BedrockAgentCoreApp()
log = app.logger

# --- Constants ---
REGION = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION', 'us-west-2')

# --- Singleton ---
_agent = None


def get_or_create_agent() -> AWSCostEstimatorAgent:
    """Get or create the cost estimation agent (singleton).

    AWSCostEstimatorAgent is the facade that owns model, tools, and MCP client.
    Creating it once avoids repeated MCP connection and model initialization.
    """
    global _agent
    if _agent is None:
        _agent = AWSCostEstimatorAgent(region=REGION)
    return _agent


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint with streaming response.

    Implements delta-based streaming following Amazon Bedrock best practices.
    """
    log.info("Invoking Cost Estimator Agent...")

    user_input = payload.get("prompt")
    prompt = COST_ESTIMATION_PROMPT.format(architecture_description=user_input)

    agent = get_or_create_agent()

    try:
        previous_output = ""

        async for event in agent.stream(prompt):
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
