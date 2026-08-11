#!/usr/bin/env python3
"""
Create an Amazon Cognito user pool that acts as the OIDC provider for
AgentCore Identity and for the Runtime's CUSTOM_JWT inbound authorizer.

The AgentCore CLI cannot create an identity provider, so this script does that
part with boto3. Everything downstream is declared in agentcore.json:

    agentcore add agent --authorizer-type CUSTOM_JWT --discovery-url ... --allowed-clients ...
    agentcore add credential --type oauth --discovery-url ... --client-id ... --client-secret ...
    agentcore deploy

Created resources:
    - User pool                       (the OIDC provider)
    - User pool domain                (needed for the token endpoint)
    - Resource server + custom scope  (agentcore/invoke)
    - App client with a secret        (machine-to-machine, client_credentials)

Usage:
    uv run python setup_cognito.py
    uv run python setup_cognito.py --force     # recreate
"""

import argparse
import json
import logging
import time
import uuid
from pathlib import Path

import boto3
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_FILE = Path("inbound_authorizer.json")
POOL_NAME_PREFIX = "agentcore-cost-estimator"
RESOURCE_SERVER_ID = "agentcore"
SCOPE_NAME = "invoke"
SCOPE = f"{RESOURCE_SERVER_ID}/{SCOPE_NAME}"
CREDENTIAL_NAME = "CostEstimatorOutboundIdentity"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open() as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def create_cognito(region: str) -> dict:
    """Create the user pool, domain, resource server and M2M app client."""
    cognito = boto3.client("cognito-idp", region_name=region)
    suffix = uuid.uuid4().hex[:8]
    pool_name = f"{POOL_NAME_PREFIX}-{suffix}"

    logger.info("Creating user pool: %s", pool_name)
    pool = cognito.create_user_pool(PoolName=pool_name)["UserPool"]
    user_pool_id = pool["Id"]

    logger.info("Creating user pool domain: %s", pool_name)
    cognito.create_user_pool_domain(UserPoolId=user_pool_id, Domain=pool_name)

    logger.info("Creating resource server: %s", RESOURCE_SERVER_ID)
    cognito.create_resource_server(
        UserPoolId=user_pool_id,
        Identifier=RESOURCE_SERVER_ID,
        Name="AgentCore API",
        Scopes=[{"ScopeName": SCOPE_NAME, "ScopeDescription": "Invoke the runtime"}],
    )

    logger.info("Creating app client (machine-to-machine)")
    client = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName="cost-estimator-m2m-client",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[SCOPE],
        AllowedOAuthFlowsUserPoolClient=True,
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"],
    )["UserPoolClient"]

    return {
        "region": region,
        "user_pool_id": user_pool_id,
        "domain": pool_name,
        "client_id": client["ClientId"],
        "client_secret": client["ClientSecret"],
        "scope": SCOPE,
        "discovery_url": (
            f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
            "/.well-known/openid-configuration"
        ),
        "token_endpoint": f"https://{pool_name}.auth.{region}.amazoncognito.com/oauth2/token",
    }


def delete_cognito(cognito_config: dict) -> None:
    """Delete the Cognito resources created by this script."""
    region = cognito_config.get("region") or boto3.Session().region_name
    cognito = boto3.client("cognito-idp", region_name=region)
    user_pool_id = cognito_config.get("user_pool_id")
    if not user_pool_id:
        return

    for step, fn in (
        ("app client", lambda: cognito.delete_user_pool_client(
            UserPoolId=user_pool_id, ClientId=cognito_config["client_id"])),
        ("domain", lambda: cognito.delete_user_pool_domain(
            UserPoolId=user_pool_id, Domain=cognito_config["domain"])),
        ("user pool", lambda: cognito.delete_user_pool(UserPoolId=user_pool_id)),
    ):
        try:
            fn()
            logger.info("Deleted %s", step)
        except Exception as e:  # noqa: BLE001 — best-effort cleanup
            logger.warning("Could not delete %s: %s", step, e)


def wait_for_oidc_endpoint(discovery_url: str, max_wait: int = 600, interval: int = 15) -> bool:
    """Wait until the OIDC discovery document is served.

    A freshly created Cognito domain can take several minutes to resolve.
    AgentCore Identity validates the discovery URL at creation time, so the
    credential must not be created before this succeeds.
    """
    logger.info("⏳ Waiting for OIDC endpoint: %s", discovery_url)
    deadline = time.time() + max_wait
    attempt = 1

    while time.time() < deadline:
        try:
            response = requests.get(discovery_url, timeout=10)
            if response.status_code == 200 and "issuer" in response.json():
                logger.info("✅ OIDC discovery document is available")
                return True
            logger.info("⏳ Attempt %d: HTTP %d", attempt, response.status_code)
        except Exception as e:  # noqa: BLE001 — endpoint may not resolve yet
            logger.info("⏳ Attempt %d: %s", attempt, e)

        time.sleep(interval)
        attempt += 1

    logger.warning("❌ OIDC endpoint not available after %ds", max_wait)
    return False


def print_next_steps(cognito_config: dict) -> None:
    """Print the AgentCore CLI commands that consume this configuration."""
    print()
    print("=" * 78)
    print("Next steps — run these in the AgentCore project directory")
    print("=" * 78)
    print()
    print("# 1. Inbound auth: a Runtime that only accepts JWT-authorized requests")
    print("agentcore add agent \\")
    print("    --name MySecureAgent \\")
    print("    --language Python --framework Strands --model-provider Bedrock \\")
    print("    --memory none \\")
    print("    --authorizer-type CUSTOM_JWT \\")
    print(f"    --discovery-url {cognito_config['discovery_url']} \\")
    print(f"    --allowed-clients {cognito_config['client_id']}")
    print()
    print("# 2. The MCP server the agent will call (also JWT protected)")
    print("agentcore add agent \\")
    print("    --name MyMcpServer \\")
    print("    --language Python --protocol MCP --build CodeZip \\")
    print("    --memory none \\")
    print("    --authorizer-type CUSTOM_JWT \\")
    print(f"    --discovery-url {cognito_config['discovery_url']} \\")
    print(f"    --allowed-clients {cognito_config['client_id']}")
    print()
    print("# 3. Outbound auth: AgentCore Identity credential provider")
    print("agentcore add credential \\")
    print(f"    --name {CREDENTIAL_NAME} \\")
    print("    --type oauth \\")
    print(f"    --discovery-url {cognito_config['discovery_url']} \\")
    print(f"    --client-id {cognito_config['client_id']} \\")
    print(f"    --client-secret {cognito_config['client_secret']} \\")
    print(f"    --scopes {cognito_config['scope']}")
    print()
    print("# 4. Create everything in AWS")
    print("agentcore deploy")
    print()
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the Cognito OIDC provider for AgentCore Identity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--force", action="store_true", help="Delete and recreate")
    parser.add_argument("--region", default=None, help="AWS region (defaults to the profile)")
    args = parser.parse_args()

    region = args.region or boto3.Session().region_name
    config = load_config()

    if config.get("cognito") and not args.force:
        logger.info("Cognito already configured (use --force to recreate)")
        print_next_steps(config["cognito"])
        return 0

    if config.get("cognito") and args.force:
        logger.info("Deleting existing Cognito resources...")
        delete_cognito(config["cognito"])
        config.pop("cognito", None)
        save_config(config)

    cognito_config = create_cognito(region)
    config["cognito"] = cognito_config
    config["credential_name"] = CREDENTIAL_NAME
    save_config(config)
    logger.info("✅ Saved configuration to %s", CONFIG_FILE)

    wait_for_oidc_endpoint(cognito_config["discovery_url"])
    print_next_steps(cognito_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
