"""
Setup Cedar-based policy for fine-grained tool access control on AgentCore Gateway.

This script creates:
1. Cognito resource server with custom scope for email sending
2. Two M2M app clients (Manager with email scope, Developer without)
3. Policy Engine with Cedar policy restricting email tool to authorized scopes
4. Attaches the policy engine to the existing gateway

Prerequisites:
- 06_identity setup complete (inbound_authorizer.json exists)
- 07_gateway setup complete (outbound_gateway.json exists)

Usage:
    uv run python 08_policy/setup_policy.py
    uv run python 08_policy/setup_policy.py --force
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Optional

import boto3
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from bedrock_agentcore_starter_toolkit.operations.policy.client import PolicyClient
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

IDENTITY_FILE = Path("../06_identity/inbound_authorizer.json")
GATEWAY_FILE = Path("../07_gateway/outbound_gateway.json")
CONFIG_FILE = Path("policy_config.json")

POLICY_ENGINE_NAME = "cost-estimator-policy-engine"
POLICY_NAME = "email-scope-policy"
RESOURCE_SERVER_IDENTIFIER = "cost-estimator"
RESOURCE_SERVER_NAME = "CostEstimatorScopes"
EMAIL_SCOPE_NAME = "email-send"
EMAIL_SCOPE_DESCRIPTION = "Permission to send cost estimation emails"


def load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r") as f:
            return json.load(f)
    return {}


def save_config(updates: Optional[dict] = None, delete_key: str = ""):
    """Update configuration file with new data."""
    config = load_config()
    if updates is not None:
        config.update(updates)
    elif delete_key:
        config.pop(delete_key, None)
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)


def load_prerequisite_configs() -> tuple[dict, dict]:
    """Load configs from step 06 and step 07."""
    if not IDENTITY_FILE.exists():
        raise FileNotFoundError(
            f"Identity config not found: {IDENTITY_FILE}\n"
            "Please run 06_identity/setup_inbound_authorizer.py first."
        )
    if not GATEWAY_FILE.exists():
        raise FileNotFoundError(
            f"Gateway config not found: {GATEWAY_FILE}\n"
            "Please run 07_gateway/setup_outbound_gateway.py first."
        )
    with IDENTITY_FILE.open("r") as f:
        identity_config = json.load(f)
    with GATEWAY_FILE.open("r") as f:
        gateway_config = json.load(f)
    return identity_config, gateway_config


def setup_cognito_clients(
    identity_config: dict, gateway_config: dict, force: bool = False
) -> dict:
    """Create Cognito resource server and two M2M app clients.

    - Manager: has invoke scope + email-send scope
    - Developer: has invoke scope only (no email-send)
    """
    config = load_config()
    if "cognito_clients" in config and not force:
        logger.info("Cognito clients already configured (use --force to recreate)")
        return config["cognito_clients"]

    user_pool_id = identity_config["cognito"]["user_pool_id"]
    token_endpoint = identity_config["cognito"]["token_endpoint"]
    original_client_id = identity_config["cognito"]["client_id"]
    # The existing scope from step 06 (used for runtime invoke)
    existing_scope = identity_config["cognito"]["scope"]

    cognito = boto3.client("cognito-idp")

    # Clean up existing resources if force
    if force and "cognito_clients" in config:
        logger.info("Cleaning up existing Cognito resources...")
        _cleanup_cognito_clients(cognito, config["cognito_clients"])

    # Step 1: Create resource server with custom email-send scope
    logger.info("Creating Cognito resource server with email-send scope...")
    try:
        cognito.create_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_IDENTIFIER,
            Name=RESOURCE_SERVER_NAME,
            Scopes=[
                {
                    "ScopeName": EMAIL_SCOPE_NAME,
                    "ScopeDescription": EMAIL_SCOPE_DESCRIPTION,
                }
            ],
        )
        logger.info("Resource server created: %s", RESOURCE_SERVER_IDENTIFIER)
    except cognito.exceptions.ClientError as e:
        if "already exists" in str(e).lower():
            logger.info("Resource server already exists, continuing...")
        else:
            raise

    email_scope = f"{RESOURCE_SERVER_IDENTIFIER}/{EMAIL_SCOPE_NAME}"

    # Step 2: Create Manager app client (invoke + email-send)
    logger.info("Creating Manager app client...")
    manager_scopes = [existing_scope, email_scope]
    manager_response = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName="CostEstimatorManager",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=manager_scopes,
        AllowedOAuthFlowsUserPoolClient=True,
    )
    manager_client = manager_response["UserPoolClient"]
    logger.info("Manager client created: %s", manager_client["ClientId"])

    # Step 3: Create Developer app client (invoke only, no email-send)
    logger.info("Creating Developer app client...")
    developer_scopes = [existing_scope]
    developer_response = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName="CostEstimatorDeveloper",
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=developer_scopes,
        AllowedOAuthFlowsUserPoolClient=True,
    )
    developer_client = developer_response["UserPoolClient"]
    logger.info("Developer client created: %s", developer_client["ClientId"])

    cognito_config = {
        "resource_server_identifier": RESOURCE_SERVER_IDENTIFIER,
        "user_pool_id": user_pool_id,
        "token_endpoint": token_endpoint,
        "original_client_id": original_client_id,
        "existing_scope": existing_scope,
        "manager": {
            "client_id": manager_client["ClientId"],
            "client_secret": manager_client["ClientSecret"],
            "scopes": " ".join(manager_scopes),
        },
        "developer": {
            "client_id": developer_client["ClientId"],
            "client_secret": developer_client["ClientSecret"],
            "scopes": " ".join(developer_scopes),
        },
    }
    save_config({"cognito_clients": cognito_config})
    logger.info("Cognito clients configuration saved")
    return cognito_config


def update_gateway_allowed_clients(
    gateway_config: dict, cognito_config: dict
) -> str:
    """Add Manager and Developer client IDs to gateway's allowedClients.

    Without this, tokens from new clients are rejected before policy evaluation.
    Returns the gateway ARN.
    """
    config = load_config()
    if "gateway_arn" in config:
        logger.info("Gateway already updated with new clients")
        return config["gateway_arn"]

    gateway_id = gateway_config["gateway"]["id"]
    region = boto3.Session().region_name
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Get current gateway to read existing authorizer config
    gateway = control_client.get_gateway(gatewayIdentifier=gateway_id)
    gateway_arn = gateway["gatewayArn"]

    current_auth = gateway.get("authorizerConfiguration", {})
    jwt_config = current_auth.get("customJWTAuthorizer", {})
    current_clients = jwt_config.get("allowedClients", [])

    # Add new client IDs
    new_clients = list(set(current_clients + [
        cognito_config["manager"]["client_id"],
        cognito_config["developer"]["client_id"],
    ]))

    logger.info("Updating gateway allowedClients: %d -> %d clients",
                len(current_clients), len(new_clients))

    updated_auth = {
        "customJWTAuthorizer": {
            "discoveryUrl": jwt_config["discoveryUrl"],
            "allowedClients": new_clients,
        }
    }

    # Build update request preserving existing fields
    update_request = {
        "gatewayIdentifier": gateway_id,
        "name": gateway["name"],
        "roleArn": gateway["roleArn"],
        "protocolType": gateway["protocolType"],
        "authorizerType": gateway["authorizerType"],
        "authorizerConfiguration": updated_auth,
    }
    # Preserve optional fields
    for field in [
        "description", "policyEngineConfiguration", "protocolConfiguration",
        "kmsKeyArn", "customTransformConfiguration",
        "interceptorConfigurations", "exceptionLevel",
    ]:
        if field in gateway:
            update_request[field] = gateway[field]

    control_client.update_gateway(**update_request)
    logger.info("Gateway allowedClients updated")

    save_config({"gateway_arn": gateway_arn})
    return gateway_arn


def setup_policy_engine(console: Console) -> dict:
    """Create policy engine, demo NL2Cedar, and create Cedar policy."""
    config = load_config()
    if "policy_engine" in config and "policy" in config:
        logger.info("Policy engine and policy already configured")
        return config

    region = boto3.Session().region_name
    policy_client = PolicyClient(region_name=region)
    gateway_arn = config["gateway_arn"]

    # Step 1: Create or get policy engine
    if "policy_engine" not in config:
        logger.info("Creating policy engine...")
        engine = policy_client.create_or_get_policy_engine(
            name=POLICY_ENGINE_NAME,
            description="Policy engine for cost estimator gateway tool access control",
        )
        engine_id = engine["policyEngineId"]
        engine_arn = engine["policyEngineArn"]
        save_config({
            "policy_engine": {"id": engine_id, "arn": engine_arn},
        })
        logger.info("Policy engine created: %s", engine_id)
    else:
        engine_id = config["policy_engine"]["id"]
        engine_arn = config["policy_engine"]["arn"]

    # Step 2: Demo NL2Cedar generation (informational only)
    logger.info("Demonstrating NL2Cedar policy generation...")
    try:
        nl_description = (
            "Allow users who have the email-send scope in their OAuth token "
            "to use the markdown_to_email tool on the gateway. "
            "Deny all other users from using the markdown_to_email tool."
        )
        generation = policy_client.generate_policy(
            policy_engine_id=engine_id,
            name="demo-nl2cedar-generation",
            resource={"arn": gateway_arn},
            content={"rawText": nl_description},
            fetch_assets=True,
        )
        console.print(Panel(
            f"[bold]Input:[/bold] {nl_description}",
            title="NL2Cedar: Natural Language Input",
        ))
        generated_policies = generation.get("generatedPolicies", [])
        for i, asset in enumerate(generated_policies):
            cedar_def = asset.get("definition", {}).get("cedar", {})
            statement = cedar_def.get("statement", "No statement generated")
            console.print(Panel(
                Syntax(statement, "cedar", theme="monokai"),
                title=f"NL2Cedar: Generated Policy {i + 1}",
            ))
        logger.info("NL2Cedar demo complete (for reference only)")
    except Exception as e:
        logger.warning("NL2Cedar demo failed (non-critical): %s", e)

    # Step 3: Create the actual Cedar policy
    if "policy" not in config:
        # The target name follows convention: GatewayName + "Target"
        # The action format is: TargetName__ToolName
        target_name = "AWSCostEstimatorGatewayTarget"
        tool_name = "markdown_to_email"
        action_name = f"{target_name}__{tool_name}"

        cedar_statement = (
            "permit(\n"
            "  principal is AgentCore::OAuthUser,\n"
            f'  action == AgentCore::Action::"{action_name}",\n'
            f'  resource == AgentCore::Gateway::"{gateway_arn}"\n'
            ")\n"
            "when {\n"
            '  principal.hasTag("scope") &&\n'
            '  principal.getTag("scope") like "*email-send*"\n'
            "};"
        )

        console.print(Panel(
            Syntax(cedar_statement, "cedar", theme="monokai"),
            title="Cedar Policy to Create",
        ))

        logger.info("Creating Cedar policy...")
        policy = policy_client.create_or_get_policy(
            policy_engine_id=engine_id,
            name=POLICY_NAME,
            definition={"cedar": {"statement": cedar_statement}},
            description=(
                "Permit markdown_to_email tool only for OAuth users "
                "whose token contains the email-send scope"
            ),
        )
        policy_id = policy["policyId"]
        policy_arn = policy["policyArn"]
        save_config({
            "policy": {
                "id": policy_id,
                "arn": policy_arn,
                "cedar_statement": cedar_statement,
            },
        })
        logger.info("Cedar policy created: %s", policy_id)

    return load_config()


def attach_policy_to_gateway() -> None:
    """Attach the policy engine to the gateway in ENFORCE mode."""
    config = load_config()
    if config.get("policy_attached"):
        logger.info("Policy engine already attached to gateway")
        return

    region = boto3.Session().region_name
    gateway_client = GatewayClient(region_name=region)
    gateway_id = None
    with GATEWAY_FILE.open("r") as f:
        gw_config = json.load(f)
        gateway_id = gw_config["gateway"]["id"]

    engine_arn = config["policy_engine"]["arn"]

    logger.info("Attaching policy engine to gateway (ENFORCE mode)...")
    gateway_client.update_gateway_policy_engine(
        gateway_identifier=gateway_id,
        policy_engine_arn=engine_arn,
        mode="ENFORCE",
    )
    save_config({"policy_attached": True})
    logger.info("Policy engine attached to gateway in ENFORCE mode")


def _cleanup_cognito_clients(cognito, cognito_config: dict) -> None:
    """Clean up Cognito resources created by this step."""
    user_pool_id = cognito_config.get("user_pool_id")
    if not user_pool_id:
        return

    for role in ["manager", "developer"]:
        client_id = cognito_config.get(role, {}).get("client_id")
        if client_id:
            try:
                cognito.delete_user_pool_client(
                    UserPoolId=user_pool_id, ClientId=client_id
                )
                logger.info("Deleted %s client: %s", role, client_id)
            except Exception as e:
                logger.warning("Failed to delete %s client: %s", role, e)

    try:
        cognito.delete_resource_server(
            UserPoolId=user_pool_id,
            Identifier=cognito_config.get(
                "resource_server_identifier", RESOURCE_SERVER_IDENTIFIER
            ),
        )
        logger.info("Deleted resource server")
    except Exception as e:
        logger.warning("Failed to delete resource server: %s", e)


def main():
    parser = argparse.ArgumentParser(
        description="Setup Cedar-based policy for AgentCore Gateway"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force recreation of resources"
    )
    args = parser.parse_args()
    console = Console()

    try:
        # Load prerequisite configs
        identity_config, gateway_config = load_prerequisite_configs()
        logger.info("Loaded prerequisite configs from step 06 and 07")

        # Step 1: Create Cognito resource server + M2M clients
        cognito_config = setup_cognito_clients(
            identity_config, gateway_config, force=args.force
        )
        logger.info("Step 1 complete: Cognito clients created")

        # Step 2: Update gateway allowedClients
        update_gateway_allowed_clients(gateway_config, cognito_config)
        logger.info("Step 2 complete: Gateway allowedClients updated")

        # Step 3: Create policy engine + Cedar policy
        setup_policy_engine(console)
        logger.info("Step 3 complete: Policy engine and Cedar policy created")

        # Step 4: Attach policy engine to gateway
        attach_policy_to_gateway()
        logger.info("Step 4 complete: Policy engine attached to gateway")

        # Show final config
        console.print_json(json.dumps(load_config()))
        console.print(Panel(
            "uv run python 08_policy/test_policy.py --role manager --address you@example.com\n"
            "uv run python 08_policy/test_policy.py --role developer --address you@example.com",
            title="Next: Test role-based access control",
        ))

    except Exception as e:
        logger.error("Setup failed: %s", e)
        raise


if __name__ == "__main__":
    main()
