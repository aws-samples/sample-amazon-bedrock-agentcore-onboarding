"""
Test Cedar-based policy enforcement on AgentCore Gateway.

Demonstrates scope-based access control:
- manager: token contains the manager scope -> Cedar permit matches -> email tool visible
- viewer:  token lacks the manager scope   -> no matching permit  -> email tool hidden

The Gateway URL and the demo scopes come from policy_demo.json, written
by setup_policy_demo.py. The policy engine and policy themselves are declared in
agentcore.json and created by `agentcore deploy`.

Usage:
    # Compare both scopes (tool visibility only, no email sent)
    uv run python test_policy.py

    # A single scope
    uv run python test_policy.py --scope manager

    # Also run the agent end-to-end and send the estimate by email
    uv run python test_policy.py --scope manager --address you@example.com
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import boto3
import requests
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from rich.console import Console
from rich.panel import Panel

# Configure logging
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

CONFIG_FILE = Path("policy_demo.json")


@tool(name="cost_estimator_tool", description="Estimate cost of AWS from architecture description")
def cost_estimator_tool(architecture_description: str) -> str:
    """Local tool: estimate AWS costs from architecture description."""
    region = boto3.Session().region_name
    cost_estimator = AWSCostEstimatorAgent(region=region)
    logger.info("Estimating costs for: %s", architecture_description)
    try:
        return cost_estimator.estimate_costs(architecture_description)
    finally:
        cost_estimator.cleanup()


def get_token_via_client_credentials(
    token_endpoint: str, client_id: str, client_secret: str, scope: str
) -> str:
    """Get an OAuth2 access token using the Cognito client_credentials flow."""
    logger.info("Requesting token from %s", token_endpoint)
    response = requests.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    logger.info("Token obtained (scope: %s)", scope)
    return response.json()["access_token"]


def collect_gateway_tools(mcp_client: MCPClient) -> list:
    """List every tool the Gateway exposes, following pagination."""
    tools = []
    pagination_token = None
    while True:
        page = mcp_client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(page)
        pagination_token = page.pagination_token
        if pagination_token is None:
            return tools


def run_for_scope(
    scope_key: str, config: dict, architecture: str, address: str | None, console: Console
):
    """Show which tools the Gateway exposes for one scope, and optionally run the agent."""
    scope = config["scopes"][scope_key]
    gateway_url = config["gateway"]["url"]

    console.print(Panel(
        f"[bold]Scope requested:[/bold] {scope}\n"
        f"[bold]Client ID:[/bold] {config['client_id']}",
        title=f"Testing as {scope_key.upper()}",
    ))

    access_token = get_token_via_client_credentials(
        token_endpoint=config["token_endpoint"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scope=scope,
    )

    def create_transport():
        return streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    mcp_client = MCPClient(create_transport)

    with mcp_client:
        gateway_tools = collect_gateway_tools(mcp_client)
        tool_names = [t.tool_name for t in gateway_tools]
        logger.info("Gateway tools: %s", tool_names)

        # With ENFORCE mode, tools the policy does not permit are hidden
        has_email = any("markdown_to_email" in name for name in tool_names)

        tool_list = "\n".join(f"  [green]✓[/green] {n}" for n in tool_names) or "  (none)"
        if not has_email:
            tool_list += (
                "\n  [yellow]✗ markdown_to_email — hidden by Cedar policy[/yellow]"
            )

        if has_email:
            verdict = "[green bold]PERMITTED[/green bold] — token scope matches the Cedar policy"
        else:
            verdict = "[yellow bold]DEFAULT-DENY[/yellow bold] — token scope matches no permit"

        console.print(Panel(
            f"[bold]Gateway tools visible with {scope}:[/bold]\n"
            f"{tool_list}\n\n"
            f"[bold]Policy decision:[/bold] {verdict}",
            title=f"Policy Effect: {scope_key.upper()}",
        ))

        if not address:
            return None

        tools = [cost_estimator_tool] + gateway_tools
        agent = Agent(
            system_prompt=(
                "You are a professional solution architect. Please estimate cost of AWS platform."
                "1. Please summarize customer's requirement to `architecture_description` in 10~50 words."
                "2. Pass `architecture_description` to 'cost_estimator_tool'."
                "3. Send estimation by `markdown_to_email`."
            ),
            tools=tools,
        )

        prompt = f"requirements: {architecture}, address: {address}"
        logger.info("Sending prompt to agent...")
        result = agent(prompt)
        console.print(Panel(
            f"[green]Agent completed for {scope_key}[/green]",
            title="Result",
        ))
        return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test Cedar policy enforcement on AgentCore Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scope",
        choices=["manager", "viewer", "both"],
        default="both",
        help="Which demo scope to request (default: both)",
    )
    parser.add_argument(
        "--architecture",
        default=(
            "A simple web application with an Application Load Balancer, "
            "2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1."
        ),
        help="Architecture description for cost estimation",
    )
    parser.add_argument(
        "--address",
        help="Email address to send the estimate to. Omit to only compare tool visibility",
    )
    args = parser.parse_args()
    console = Console()

    if not CONFIG_FILE.exists():
        logger.error(
            "%s not found. Run `uv run python setup_policy_demo.py` first.", CONFIG_FILE
        )
        return 1

    with CONFIG_FILE.open() as f:
        config = json.load(f)

    scopes = ["manager", "viewer"] if args.scope == "both" else [args.scope]

    for scope_key in scopes:
        console.print()
        console.rule(f"Testing {scope_key.upper()} scope")
        run_for_scope(scope_key, config, args.architecture, args.address, console)
        console.print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
