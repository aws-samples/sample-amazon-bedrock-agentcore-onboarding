"""
AgentCore Runtime entrypoint that calls a JWT-protected MCP server.

Two different concerns meet in this file, and only one of them is visible here.

**Inbound auth is not in this file.** The Runtime is declared with
``--authorizer-type CUSTOM_JWT``, so AgentCore validates the caller's JWT before
this code ever runs. Inbound auth is a Runtime setting, not agent code.

**Outbound auth is in this file.** This agent calls an MCP server that is also
JWT protected. It asks AgentCore Identity for that token with the
``@requires_access_token`` decorator, using the credential provider declared by
``agentcore add credential --type oauth``.

The token never reaches the model: the tool the model sees delegates to an inner
function, and the decorator injects the token into that inner function only.
"""

import json
import os
import urllib.parse

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

app = BedrockAgentCoreApp()
log = app.logger

# `agentcore deploy` injects CREDENTIAL_<NAME>_NAME for each declared credential,
# so the provider name never has to be hard-coded here.
OAUTH_PROVIDER = next(
    (v for k, v in os.environ.items() if k.startswith("CREDENTIAL_") and k.endswith("_NAME")),
    "",
)
# Both supplied through runtimes[].envVars in agentcore.json
OAUTH_SCOPE = os.environ.get("MCP_SCOPE", "agentcore/invoke")
MCP_RUNTIME_ARN = os.environ.get("MCP_RUNTIME_ARN", "")

SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the add_numbers tool for any arithmetic "
    "instead of calculating it yourself, and report the tool result verbatim."
)


def mcp_invocation_url(runtime_arn: str) -> str:
    """Build the MCP endpoint URL of an MCP-protocol Runtime."""
    region = runtime_arn.split(":")[3]
    encoded = urllib.parse.quote(runtime_arn, safe="")
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{encoded}/invocations?qualifier=DEFAULT"
    )


@requires_access_token(
    provider_name=OAUTH_PROVIDER,
    scopes=[OAUTH_SCOPE],
    auth_flow="M2M",
    force_authentication=False,
)
def _call_mcp(tool_name: str, arguments: dict, access_token: str = "") -> str:
    """Call one tool on the protected MCP server.

    AgentCore Identity injects ``access_token``; no caller passes it in.
    """
    log.info("MCP call %s via provider %s", tool_name, OAUTH_PROVIDER)

    def transport():
        return streamablehttp_client(
            mcp_invocation_url(MCP_RUNTIME_ARN),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    with MCPClient(transport) as client:
        result = client.call_tool_sync(
            tool_use_id=f"{tool_name}-1", name=tool_name, arguments=arguments
        )
        return json.dumps(result, default=str)


@tool(name="add_numbers", description="Add two integers using the remote MCP server")
def add_numbers(a: int, b: int) -> str:
    """Expose the MCP server's add_numbers tool without leaking the token."""
    return _call_mcp("add_numbers", {"a": a, "b": b})


_agent = None


def get_or_create_agent() -> Agent:
    """Create the agent once and reuse it across invocations."""
    global _agent
    if _agent is None:
        _agent = Agent(system_prompt=SYSTEM_PROMPT, tools=[add_numbers])
    return _agent


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entrypoint with streaming response."""
    prompt = payload.get("prompt", "")
    agent = get_or_create_agent()

    previous = ""
    async for event in agent.stream_async(prompt):
        if "data" not in event:
            continue
        current = str(event["data"])
        if current.startswith(previous):
            delta = current[len(previous):]
            if delta:
                previous = current
                yield delta
        else:
            previous = current
            yield current


if __name__ == "__main__":
    app.run()
