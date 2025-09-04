"""
既存のCognito設定を使用してAgentCore IdentityのOAuth2認証プロバイダーをセットアップ

このスクリプトは、ゲートウェイ設定からの既存のCognito M2M OAuth
セットアップと統合されるOAuth2認証プロバイダーを作成します。このプロバイダーにより、
AgentCore Identityは認証されたAPIコール用のアクセストークンを安全に管理できます。

前提条件:
- bedrock-agentcore-control権限でAWS認証情報が設定済み

使用方法:
    uv run python 03_identity/setup_inbound_authorizer.py
"""

import json
import boto3
import logging
import argparse
import time
from pathlib import Path
from typing import Optional
import urllib.parse
import requests
from rich.console import Console
from rich.panel import Panel
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
import yaml


# 明確なデバッグのためのログ設定を構成
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

PROVIDER_NAME = "inbound-identity-for-cost-estimator-agent"
CONFIG_FILE = Path("inbound_authorizer.json")

def setup_oauth2_credential_provider(provider_name: str = PROVIDER_NAME, force: bool = False) -> dict:
    """
    AgentCore Identity用のOAuth2認証プロバイダーをセットアップ。
    
    この関数は以下を実行：
    1. Cognitoユーザープールとアプリクライアントを作成
    2. CognitoディスカバリーURLを使用してOAuth2認証プロバイダーを作成
    3. 設定をinbound_authorizer.jsonに保存
    
    Args:
        provider_name: 認証プロバイダーの名前
        force: リソースの再作成を強制するかどうか

    Returns:
        dict: 設定
    """

    config = load_config()
    region = boto3.Session().region_name

    has_cognito = config and 'cognito' in config
    has_provider = config and 'provider' in config

    identity_client = boto3.client('bedrock-agentcore-control', region_name=region)

    # すべてが完了しており強制しない場合、要約を表示して終了
    if config and has_cognito and has_provider and not force:
        logger.info("All components already configured (use --force to recreate)")
        return config
    elif config:
        if has_provider and force:
            logger.info("Delete existing OAuth2 credential provider...")
            identity_client.delete_oauth2_credential_provider(name=provider_name)
            save_config(delete_key="provider")
            has_provider = False
        if has_cognito and force:
            logger.info("Delete existing Cognito OAuth authorizer...")
            cleanup_cognito_resources(config['cognito'])
            save_config(delete_key="cognito")
            has_cognito = False
    
    cognito_config = {}
    if not has_cognito:
        logger.info("Creating Cognito OAuth authorizer...")
        gateway_client = GatewayClient(region_name=region)
        # Gateway ClientからCognitoでOAuthオーソライザーを作成するためのシンプルなインターフェイスを使用
        cognito_result = gateway_client.create_oauth_authorizer_with_cognito("InboundAuthorizerForCostEstimatorAgent")
        user_pool_id = cognito_result['client_info']['user_pool_id']
        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
        cognito_config = {
            "client_id": cognito_result['client_info']['client_id'],
            "client_secret": cognito_result['client_info']['client_secret'],
            "token_endpoint": cognito_result['client_info']['token_endpoint'],
            "discovery_url": discovery_url,
            "scope": cognito_result['client_info']['scope'],
            "user_pool_id": user_pool_id,
            "region": region
        }
        save_config({"cognito" : cognito_config})
        logger.info("✅ Cognito configuration saved")

    provider_config = {}
    if not has_provider:
        logger.info("Creating Identity Provider ...")
        # 新しい認証プロバイダー設定を作成
        # https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CustomOauth2ProviderConfigInput.html
        # https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_Oauth2Discovery.html
        wait_for_oidc_endpoint(discovery_url)
        oauth2_config = {
            'customOauth2ProviderConfig': {
                'clientId': cognito_config['client_id'],
                'clientSecret': cognito_config['client_secret'],
                'oauthDiscovery': {
                    'discoveryUrl': cognito_config['discovery_url']
                }
            }
        }

        # APIリファレンス: https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateOauth2CredentialProvider.html
        response = identity_client.create_oauth2_credential_provider(
            name=provider_name,
            credentialProviderVendor='CustomOauth2',
            oauth2ProviderConfigInput=oauth2_config
        )

        provider_config = {
            "name": provider_name,
            "arn" : response['credentialProviderArn']
        }
        save_config({"provider": provider_config})
        logger.info("✅ Provider configuration saved")
        
        return load_config()


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open('r') as f:
                config = json.load(f)
        return config
    else:
        return {}


def save_config(updates: Optional[dict]=None, delete_key: str=""):
    """新しいデータで設定ファイルを更新"""
    config = load_config()
    
    if updates is not None:
        config.update(updates)
    elif delete_key:
        del config[delete_key]
    
    with CONFIG_FILE.open('w') as f:
        json.dump(config, f, indent=2)


def cleanup_cognito_resources(cognito_config):
    """Cognitoリソースを明示的にクリーンアップ"""
    if not cognito_config.get('user_pool_id'):    
        try:
            cognito_client = boto3.client('cognito-idp')
            user_pool_id = cognito_config['user_pool_id']

            cognito_client.delete_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=cognito_config['client_id']
            )

            user_pool_details = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            domain = user_pool_details.get("UserPool", {}).get("Domain")
            
            if domain:
                cognito_client.delete_user_pool_domain(Domain=domain, UserPoolId=user_pool_id)

            cognito_client.update_user_pool(
                UserPoolId=user_pool_id,
                DeletionProtection='INACTIVE'
            )

            cognito_client.delete_user_pool(UserPoolId=user_pool_id)
            
        except Exception as e:
            logger.warning(f"Cognito cleanup error: {e}")


def wait_for_oidc_endpoint(oidc_url, max_wait=600, interval=30):
    """OIDCディスカバリーエンドポイントが利用可能になるまで待機
    
    実世界のテストに基づくと、DNS伝播とサービス初期化の遅延のため、
    OIDCエンドポイントが利用可能になるまでに5分以上かかる可能性があります。
    """
    start_time = time.time()
    attempt = 1
    
    logger.info(f"⏳ Waiting for OIDC endpoint: {oidc_url}")
    logger.info(f"⏳ Timeout: {max_wait}s, Check interval: {interval}s")
    
    while time.time() - start_time < max_wait:
        response = requests.get(oidc_url, timeout=10)
        logger.info(f"⏳ Attempt {attempt}: HTTP {response.status_code}")
        
        # HTTPエラーステータスコード（4xx、5xx）に対して例外を発生
        response.raise_for_status()
        
        if response.status_code == 200:
            elapsed = time.time() - start_time
            logger.info(f"✅ OIDC endpoint available after {elapsed:.1f}s")
            # 実際に有効なJSONかどうかを検証
            try:
                json_data = response.json()
                if 'issuer' in json_data:
                    logger.info("✅ OIDC discovery document is valid")
                    return True
                else:
                    logger.warning("⚠️ OIDC response missing 'issuer' field")
            except ValueError:
                logger.warning("⚠️ OIDC response is not valid JSON")
        
        remaining = max_wait - (time.time() - start_time)
        if remaining > interval:
            logger.info(f"⏳ Waiting {interval}s... ({remaining:.0f}s remaining)")
            time.sleep(interval)
            attempt += 1
        else:
            break
    
    logger.warning(f"❌ OIDC endpoint not available after {max_wait}s")
    return False


def main():
    parser = argparse.ArgumentParser(description='Create AgentCore Identity for Runtime')
    parser.add_argument('--force', action='store_true', help='Force recreation of resources')
    args = parser.parse_args()
    console = Console()

    runtime_path = Path("../02_runtime/.bedrock_agentcore.yaml")
    if not runtime_path.exists():
        logger.warning("Please deploy Runtime before setting Identity.")
        return None
    
    try:
        config = setup_oauth2_credential_provider(force=args.force)
    except Exception as e:
        logger.warning("❌ Setup Credential Provider failed:")
        logger.exception(e)

    if config and "runtime" not in config:
        logger.info("Creating Runtime with Identity...")
        with runtime_path.open() as f:
            runtime_config = yaml.safe_load(f) or {}

        agent_name = runtime_config.get("default_agent")
        secure_agent_name = f'{agent_name}_with_identity'
        aws_config = runtime_config.get("agents").get(agent_name).get("aws")
        ecr_repository = aws_config.get("ecr_repository")
        network_mode = aws_config.get("network_configuration").get("network_mode")
        execution_role = aws_config.get("execution_role")
        region = aws_config.get("region")
        authorizer_config = {
            "customJWTAuthorizer": {
                "discoveryUrl" : config["cognito"]["discovery_url"],
                "allowedClients" : [config["cognito"]["client_id"]]
            }
        }

        deploy_client = boto3.client('bedrock-agentcore-control', region_name=region)
        response = deploy_client.create_agent_runtime(
            agentRuntimeName=secure_agent_name,
            agentRuntimeArtifact={
                "containerConfiguration" : {
                    "containerUri": f"{ecr_repository}:latest"
                }
            },
            networkConfiguration={"networkMode": network_mode},
            roleArn=execution_role,
            authorizerConfiguration=authorizer_config

        )

        runtime_id = response['agentRuntimeId']
        runtime_arn = response['agentRuntimeArn']
        # https://docs.aws.amazon.com/ja_jp/bedrock-agentcore/latest/devguide/runtime-mcp.html
        escaped_arn = urllib.parse.quote(runtime_arn, safe='')
        url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
        save_config({
            "runtime": {
                "id": runtime_id,
                "name": secure_agent_name,
                "url": url
            }
        })
        logger.info("✅ Runtime configuration saved")

    console.print_json(json.dumps(load_config()))
    console.print(Panel("uv run python test_identity_agent.py", title="Let's test agent with identity!"))


if __name__ == "__main__":
    main()
