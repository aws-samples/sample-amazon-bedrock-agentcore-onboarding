"""
Test Cedar-based policy enforcement on AgentCore Gateway.

Demonstrates scope-based access control:
- Manager: token contains manager scope -> Cedar permit matches -> can send emails
- Developer: token lacks manager scope -> no matching permit -> email tool hidden

Usage:
    uv run python 08_policy/test_policy.py --role manager --address you@example.com
    uv run python 08_policy/test_policy.py --role developer --address you@example.com
    uv run python 08_policy/test_policy.py --role both --address you@example.com
"""

import json
import os
import sys
import logging
import argparse
import boto3
import requests
from strands import Agent
from strands import tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from rich.console import Console
from rich.panel import Panel
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import from 01_code_interpreter
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "01_code_interpreter"))
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

POLICY_CONFIG_FILE = Path("policy_config.json")
GATEWAY_CONFIG_FILE = Path("../07_gateway/outbound_gateway.json")


@tool(name="cost_estimator_tool", description="Estimate cost of AWS from architecture description")
def cost_estimator_tool(architecture_description: str) -> str:
    """Local tool: estimate AWS costs from architecture description."""
    region = boto3.Session().region_name
    cost_estimator = AWSCostEstimatorAgent(region=region)
    logger.info("Estimating costs for: %s", architecture_description)
    return cost_estimator.estimate_costs(architecture_description)


def get_token_via_client_credentials(
    token_endpoint: str, client_id: str, client_secret: str, scopes: str
) -> str:
    """Get OAuth2 access token using Cognito client_credentials flow."""
    logger.info("Requesting token from %s", token_endpoint)
    response = requests.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scopes,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data["access_token"]
    logger.info("Token obtained (scopes: %s)", scopes)
    return access_token


def run_agent_with_role(role: str, architecture: str, address: str, console: Console):
    """Run the agent with a specific role's credentials."""
    # Load configs
    with POLICY_CONFIG_FILE.open("r") as f:
        policy_config = json.load(f)
    with GATEWAY_CONFIG_FILE.open("r") as f:
        gateway_config = json.load(f)

    cognito = policy_config["cognito_clients"]
    role_config = cognito[role]
    gateway_url = gateway_config["gateway"]["url"]

    console.print(Panel(
        f"[bold]Role:[/bold] {role.upper()}\n"
        f"[bold]Client ID:[/bold] {role_config['client_id']}\n"
        f"[bold]Scopes:[/bold] {role_config['scopes']}",
        title=f"Testing as {role.upper()}",
    ))

    # Get access token for this role
    access_token = get_token_via_client_credentials(
        token_endpoint=cognito["token_endpoint"],
        client_id=role_config["client_id"],
        client_secret=role_config["client_secret"],
        scopes=role_config["scopes"],
    )

    # Create MCP client with bearer token
    def create_transport():
        return streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    mcp_client = MCPClient(create_transport)

    # Build agent with local + gateway tools
    tools = [cost_estimator_tool]
    with mcp_client:
        # Paginate through all gateway tools
        more_tools = True
        pagination_token = None
        while more_tools:
            tmp_tools = mcp_client.list_tools_sync(pagination_token=pagination_token)
            tools.extend(tmp_tools)
            if tmp_tools.pagination_token is None:
                more_tools = False
            else:
                pagination_token = tmp_tools.pagination_token

        tool_names = [t.tool_name for t in tools]
        logger.info("Available tools: %s", tool_names)

        # Show policy effect: which tools are visible to this role?
        # With ENFORCE mode, unauthorized tools are hidden from the list
        has_email = any("markdown_to_email" in name for name in tool_names)
        local_tools = [n for n in tool_names if "___" not in n]
        gateway_tools = [n for n in tool_names if "___" in n]

        tool_list = "\n".join(f"  [green]✓[/green] {n}" for n in local_tools)
        if gateway_tools:
            tool_list += "\n" + "\n".join(
                f"  [green]✓[/green] {n}" for n in gateway_tools
            )
        else:
            tool_list += (
                "\n  [yellow]✗ markdown_to_email — hidden by Cedar policy[/yellow]"
            )

        if has_email:
            verdict = "[green bold]PERMITTED[/green bold] — token scope matches Cedar policy"
        else:
            verdict = "[yellow bold]DEFAULT-DENY[/yellow bold] — token scope does not match any permit"

        console.print(Panel(
            f"[bold]Tools visible to {role.upper()}:[/bold]\n"
            f"{tool_list}\n\n"
            f"[bold]Policy decision:[/bold] {verdict}",
            title=f"Policy Effect: {role.upper()}",
        ))

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
            f"[green]Agent completed successfully for {role.upper()}[/green]",
            title="Result",
        ))
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Test Cedar policy enforcement on AgentCore Gateway"
    )
    parser.add_argument(
        "--role",
        type=str,
        choices=["manager", "developer", "both"],
        default="both",
        help="Role to test (default: both)",
    )
    parser.add_argument(
        "--architecture",
        type=str,
        default=(
            "A simple web application with an Application Load Balancer, "
            "2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1."
        ),
        help="Architecture description for cost estimation",
    )
    parser.add_argument(
        "--address",
        type=str,
        required=True,
        help="Email address to send estimation",
    )
    args = parser.parse_args()
    console = Console()

    roles = ["manager", "developer"] if args.role == "both" else [args.role]

    for role in roles:
        console.print()
        console.rule(f"Testing {role.upper()} role")
        run_agent_with_role(role, args.architecture, args.address, console)
        console.print()


if __name__ == "__main__":
    main()
