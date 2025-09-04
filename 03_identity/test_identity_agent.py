"""
cost_estimator_agent_with_identityを呼び出してAgentCore Identityをテスト

このスクリプトは以下の方法を実演します：
1. AgentCore IdentityからOAuthトークンを取得する
2. 取得したトークンでランタイムを呼び出す
"""

import json
import base64
import logging
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import requests
from strands import Agent
from strands import tool
from bedrock_agentcore.identity.auth import requires_access_token

# より詳細な出力でログを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


CONFIG_FILE = Path("inbound_authorizer.json")
OAUTH_PROVIDER = ""
OAUTH_SCOPE = ""
RUNTIME_URL = ""
BASE64_BLOCK_SIZE = 4 # Base64エンコーディングは4文字ブロックでデータを処理
with CONFIG_FILE.open('r') as f:
    config = json.load(f)
    OAUTH_PROVIDER = config["provider"]["name"]
    OAUTH_SCOPE = config["cognito"]["scope"]
    RUNTIME_URL = config["runtime"]["url"]


def log_jwt_token_details(access_token: str) -> None:
    """
    Base64デコーディングを使用してデバッグ目的でJWTトークン内容をログ出力。
    
    Args:
        access_token: JWTアクセストークン
    
    Note:
        JWTトークンは3つの部分（ヘッダー、ペイロード、署名）で構成されます。
        セキュリティ上の理由で、署名部分はデコードされません。
    """
    # Parse and log JWT token parts for debugging
    token_parts = access_token.split(".")
    for i, part in enumerate(token_parts[:2]):  # 署名ではなく、ヘッダーとペイロードのみをデコード
        try:
            # 必要に応じてパディングを追加（JWT Base64エンコーディングは末尾の'='文字を省略する可能性がある）
            num_padding_chars = BASE64_BLOCK_SIZE - (len(part) % BASE64_BLOCK_SIZE)
            if num_padding_chars != BASE64_BLOCK_SIZE:
                part_for_decode = part + '=' * num_padding_chars
            else:
                part_for_decode = part

            decoded = base64.b64decode(part_for_decode)
            logger.info(f"\tToken part {i}: {json.loads(decoded.decode())}")
        except Exception as e:
            logger.error(f"\t❌ Failed to decode token part {i}: {e}")


# 認証デコレーター付き内部関数
@requires_access_token(
    provider_name=OAUTH_PROVIDER,
    scopes=[OAUTH_SCOPE],
    auth_flow="M2M",
    force_authentication=False
)
async def _cost_estimator_with_auth(architecture_description: str, access_token: str = None) -> str:
    """認証を伴う実際のAPI呼び出しを処理する内部関数"""
    session_id = f"runtime-with-identity-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"

    if access_token:
        logger.info("✅ Successfully load the access token from AgentCore Identity!")
        # デバッグ用にJWTトークン部分を解析してログ出力
        log_jwt_token_details(access_token)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        "X-Amzn-Trace-Id": session_id,
    }

    response = requests.post(
        RUNTIME_URL,
        headers=headers,
        data=json.dumps({"prompt": architecture_description})
    )

    response.raise_for_status()
    return response.text


# LLMに公開されるツール関数（access_tokenパラメーターなし）
@tool(
    name="cost_estimator_tool",
    description="Estimate cost of AWS from architecture description"
)
async def cost_estimator_tool(architecture_description: str) -> str:
    """
    アーキテクチャ説明に基づいてAWSコストを見積もり。

    Args:
        architecture_description: コスト見積もり対象のAWSアーキテクチャの説明

    Returns:
        文字列としてのコスト見積もり結果
    """
    # 認証付きで内部関数を呼び出し
    # エージェントからアクセストークン引数を隠すために内部関数を呼び出し
    return await _cost_estimator_with_auth(architecture_description)


async def main():
    """メインテスト関数"""
    # コマンドライン引数を解析
    parser = argparse.ArgumentParser(description='Test AgentCore Gateway with different methods')
    parser.add_argument(
        '--architecture',
        type=str,
        default="A simple web application with an Application Load Balancer, 2 EC2 t3.medium instances, and an RDS MySQL database in us-east-1.",
        help='Architecture description for cost estimation. Default: A simple web application with ALB, 2 EC2 instances, and RDS MySQL'
    )
    args = parser.parse_args()

    agent = Agent(
        system_prompt=(
            "You are a professional solution architect. "
            "You will receive architecture descriptions or requirements from customers. "
            "Please provide estimate by using 'cost_estimator_tool'"
        ),
        tools=[cost_estimator_tool]
    )

    logger.info("Invoke agent that calls Runtime with Identity...")
    await agent.invoke_async(args.architecture)
    logger.info("✅ Successfully called agent!")


if __name__ == "__main__":
    asyncio.run(main())
