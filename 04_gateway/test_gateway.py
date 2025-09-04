"""
aws_cost_estimationツールを呼び出してAgentCore Gatewayをテスト

このスクリプトは以下の方法を実演します：
1. CognitoからOAuthトークンを取得する
2. GatewayのMCPエンドポイントを呼び出す
3. aws_cost_estimationツールを呼び出す
"""

import json
import os
import sys
import logging
import argparse
import asyncio
from pathlib import Path
import boto3
from strands import Agent
from strands import tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.identity.auth import requires_access_token

# より詳細な出力でログを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 01_code_interpreterからインポートするために親ディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "01_code_interpreter"))
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

IDENTITY_CONFIG_FILE = Path("../03_identity/inbound_authorizer.json")
GATEWAY_CONFIG_FILE = Path("outbound_gateway.json")
OAUTH_PROVIDER = ""
OAUTH_SCOPE = ""
GATEWAY_URL = ""
with IDENTITY_CONFIG_FILE.open('r') as f:
    config = json.load(f)
    OAUTH_PROVIDER = config["provider"]["name"]
    OAUTH_SCOPE = config["cognito"]["scope"]

with GATEWAY_CONFIG_FILE.open('r') as f:
    config = json.load(f)
    GATEWAY_URL = config["gateway"]["url"]


@tool(name="cost_estimator_tool", description="Estimate cost of AWS from architecture description")
def cost_estimator_tool(architecture_description: str) -> str:
    region = boto3.Session().region_name
    cost_estimator = AWSCostEstimatorAgent(region=region)
    logger.info(f"We will estimate about {architecture_description}")
    result = cost_estimator.estimate_costs(architecture_description)
    return result

@requires_access_token(
    provider_name= OAUTH_PROVIDER,
    scopes= [OAUTH_SCOPE],
    auth_flow= "M2M",
    force_authentication= False)
async def get_access_token(access_token):
    """Helper function to get access token"""
    if access_token:
        logger.info("✅ Successfully loaded the access token!")
    return access_token

def estimate_and_send(architecture_description, address):
    logger.info("Testing Gateway with MCP client (Strands Agents)...")

    # Get the access token first
    access_token = asyncio.run(get_access_token())
    # Create the transport callable that returns the HTTP client directly
    def create_transport():
        return streamablehttp_client(
            GATEWAY_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    mcp_client = MCPClient(create_transport)
    logger.info("Prepare agent's tools...")
    tools = [cost_estimator_tool]
    with mcp_client:
        more_tools = True
        pagination_token = None
        while more_tools:
            tmp_tools = mcp_client.list_tools_sync(pagination_token=pagination_token)
            tools.extend(tmp_tools)
            if tmp_tools.pagination_token is None:
                more_tools = False
            else:
                more_tools = True 
                pagination_token = tmp_tools.pagination_token

        _names = [tool.tool_name for tool in tools]
        logger.info(f"Found the following tools: {_names}")

        logger.info("\nAsking agent to estimate AWS costs...")
        agent = Agent(
            system_prompt=(
                "Your are a professional solution architect. Please estimate cost of AWS platform."
                "1. Please summarize customer's requirement to `architecture_description` in 10~50 words."
                "2. Pass `architecture_description` to 'cost_estimator_tool'."
                "3. Send estimation by `markdown_to_email`."
            ),
            tools=tools
        )
        
        # Test by asking the agent to use the aws_cost_estimation tool

        prompt = f"requirements: {architecture_description}, address: {address}"
        result = agent(prompt) 
        logger.info("✅ Successfully called agent!")
        
        return result


def main():
    """Main test function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test AgentCore Gateway')
    parser.add_argument(
        '--architecture',
        type=str,
        default="A simple web application with an Application Load Balancer, 2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1.",
        help='Architecture description for cost estimation.'
    )
    parser.add_argument(
        '--address',
        type=str,
        help='Email address to send estimation'
    )

    args = parser.parse_args()
    
    try:
        estimate_and_send(args.architecture, args.address)
    except Exception as e:
        logger.error(f"❌ Error occurred: {e}")

if __name__ == "__main__":
    main()
