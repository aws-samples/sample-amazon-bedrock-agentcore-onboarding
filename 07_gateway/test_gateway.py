"""
Call the AgentCore Gateway over MCP and let an agent use its tools.

Why there is no ``@requires_access_token`` here
-----------------------------------------------
AgentCore Gateway completes both ends of its own auth:

* **inbound** — the Gateway validates the caller's JWT (``--authorizer-type CUSTOM_JWT``)
* **outbound** — the Gateway invokes the Lambda target with its own IAM role

So the caller only has to present a token. It gets that token from the authorization
server directly, exactly as the AgentCore documentation shows for a CLI-created
Gateway. ``@requires_access_token`` belongs in an agent running *on* AgentCore
Runtime that needs to reach an external resource itself — see Lab 6.

Usage:
    uv run python test_gateway.py --list-tools
    uv run python test_gateway.py --architecture '...' --address you@example.com
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import requests
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# The base agent lives under agents/ and uses flat imports (from config import ...),
# so its directory has to be on sys.path.
AGENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "agents" / "CostEstimatorAgent" / "app" / "CostEstimatorAgent"
)
sys.path.insert(0, str(AGENT_DIR))
from cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

IDENTITY_CONFIG_FILE = Path("../06_identity/inbound_authorizer.json")
PROJECT_DIR = Path("../agents/MyGatewayProject")

DEFAULT_ARCHITECTURE = (
    "A simple web application with an Application Load Balancer, "
    "2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1."
)

SYSTEM_PROMPT = (
    "You are a professional solution architect. Estimate the AWS cost with "
    "'cost_estimator_tool', then send the estimate as an email using the Gateway's "
    "markdown_to_email tool."
)


def load_cognito() -> dict:
    """Read the Cognito settings written by 06_identity/setup_cognito.py."""
    if not IDENTITY_CONFIG_FILE.exists():
        raise SystemExit(
            f"{IDENTITY_CONFIG_FILE} not found. "
            "Run `uv run python setup_cognito.py` in 06_identity first."
        )
    with IDENTITY_CONFIG_FILE.open() as f:
        return json.load(f)["cognito"]


def load_gateway_url(project_dir: Path) -> str:
    """Read the Gateway's MCP endpoint from agentcore/.cli/deployed-state.json.

    The CLI nests gateways under ``resources.mcp.gateways``; older versions put
    them directly under ``resources.gateways``. Both shapes are accepted. The
    stored ``gatewayUrl`` already ends in ``/mcp``, so the suffix is only added
    when it is missing.
    """
    state_path = project_dir / "agentcore" / ".cli" / "deployed-state.json"
    if not state_path.exists():
        raise SystemExit(
            f"{state_path} not found. Run `agentcore deploy` in the project directory first."
        )
    with state_path.open() as f:
        state = json.load(f)

    for target in state.get("targets", {}).values():
        resources = target.get("resources", {})
        containers = [resources, resources.get("mcp", {})]
        for container in containers:
            for gateway in (container.get("gateways") or {}).values():
                url = gateway.get("gatewayUrl")
                if url:
                    url = url.rstrip("/")
                    return url if url.endswith("/mcp") else url + "/mcp"

    raise SystemExit("No deployed gateway found. Run `agentcore deploy` first.")


def get_access_token(cognito: dict) -> str:
    """Get a Cognito access token with the client-credentials (M2M) flow."""
    response = requests.post(
        cognito["token_endpoint"],
        data={
            "grant_type": "client_credentials",
            "client_id": cognito["client_id"],
            "client_secret": cognito["client_secret"],
            "scope": cognito["scope"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    logger.info("✅ Access token obtained (scope: %s)", cognito["scope"])
    return response.json()["access_token"]


def build_mcp_client(gateway_url: str, access_token: str) -> MCPClient:
    """Build an MCP client that presents the bearer token to the Gateway."""
    def transport():
        return streamablehttp_client(
            gateway_url, headers={"Authorization": f"Bearer {access_token}"}
        )

    return MCPClient(transport)


def collect_gateway_tools(mcp_client: MCPClient) -> list:
    """List every tool the Gateway exposes, following pagination."""
    tools, token = [], None
    while True:
        page = mcp_client.list_tools_sync(pagination_token=token)
        tools.extend(page)
        token = getattr(page, "pagination_token", None)
        if not token:
            return tools


@tool(name="cost_estimator_tool", description="Estimate cost of AWS from architecture description")
def cost_estimator_tool(architecture_description: str) -> str:
    """Estimate AWS costs locally with the base agent."""
    logger.info("Estimating cost for: %s", architecture_description)
    estimator = AWSCostEstimatorAgent()
    try:
        return estimator.estimate_costs(architecture_description)
    finally:
        estimator.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Use the AgentCore Gateway's tools from an agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--architecture",
        default=DEFAULT_ARCHITECTURE,
        help="Architecture description to estimate. The agent answers in its language",
    )
    parser.add_argument("--address", help="Email address to send the estimate to")
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Only list the tools the Gateway exposes, then exit",
    )
    args = parser.parse_args()

    cognito = load_cognito()
    gateway_url = load_gateway_url(PROJECT_DIR)
    logger.info("Gateway MCP endpoint: %s", gateway_url)

    token = get_access_token(cognito)
    mcp_client = build_mcp_client(gateway_url, token)

    with mcp_client:
        gateway_tools = collect_gateway_tools(mcp_client)
        logger.info("Gateway exposes %d tool(s):", len(gateway_tools))
        for t in gateway_tools:
            logger.info("  - %s", t.tool_name)

        if args.list_tools:
            return 0

        prompt = args.architecture
        if args.address:
            prompt += f" Send the estimate to {args.address}."

        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[cost_estimator_tool, *gateway_tools],
        )
        agent(prompt)

    logger.info("✅ Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
