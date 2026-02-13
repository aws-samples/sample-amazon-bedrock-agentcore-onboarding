"""
Clean up all resources created by 08_policy in reverse dependency order.

Cleanup order:
1. Detach policy engine from gateway (update gateway to remove policy config)
2. Restore gateway's allowedClients to original (step-06 client only)
3. Delete all policies, then the policy engine
4. Delete Cognito app clients (manager, developer)
5. Delete Cognito resource server
6. Remove policy_config.json

Usage:
    uv run python 08_policy/clean_resources.py
"""

import json
import os
from pathlib import Path

import boto3
from bedrock_agentcore_starter_toolkit.operations.policy.client import PolicyClient

POLICY_CONFIG_FILE = Path("policy_config.json")
GATEWAY_CONFIG_FILE = Path("../07_gateway/outbound_gateway.json")


def clean_resources():
    """Clean up all resources created by 08_policy (Policy)."""
    if not POLICY_CONFIG_FILE.exists():
        print("No policy_config.json found, nothing to clean")
        return

    with POLICY_CONFIG_FILE.open("r", encoding="utf-8") as f:
        config = json.load(f)

    region = boto3.Session().region_name
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Step 1: Detach policy engine from gateway
    if config.get("policy_attached") and GATEWAY_CONFIG_FILE.exists():
        with GATEWAY_CONFIG_FILE.open("r") as f:
            gw_config = json.load(f)
        gateway_id = gw_config["gateway"]["id"]
        print(f"Detaching policy engine from gateway {gateway_id}...")
        try:
            gateway = control_client.get_gateway(gatewayIdentifier=gateway_id)
            update_request = {
                "gatewayIdentifier": gateway_id,
                "name": gateway["name"],
                "roleArn": gateway["roleArn"],
                "protocolType": gateway["protocolType"],
                "authorizerType": gateway["authorizerType"],
            }
            # Preserve fields except policyEngineConfiguration
            for field in [
                "description", "authorizerConfiguration", "protocolConfiguration",
                "kmsKeyArn", "customTransformConfiguration",
                "interceptorConfigurations", "exceptionLevel",
            ]:
                if field in gateway:
                    update_request[field] = gateway[field]
            # Omit policyEngineConfiguration to detach
            control_client.update_gateway(**update_request)
            print("Policy engine detached from gateway")
        except Exception as e:
            print(f"Warning: Failed to detach policy engine: {e}")

    # Step 2: Restore gateway's allowedClients to original
    cognito_clients = config.get("cognito_clients", {})
    original_client_id = cognito_clients.get("original_client_id")
    if original_client_id and GATEWAY_CONFIG_FILE.exists():
        with GATEWAY_CONFIG_FILE.open("r") as f:
            gw_config = json.load(f)
        gateway_id = gw_config["gateway"]["id"]
        print("Restoring gateway allowedClients to original client only...")
        try:
            gateway = control_client.get_gateway(gatewayIdentifier=gateway_id)
            jwt_config = gateway.get("authorizerConfiguration", {}).get(
                "customJWTAuthorizer", {}
            )
            restored_auth = {
                "customJWTAuthorizer": {
                    "discoveryUrl": jwt_config["discoveryUrl"],
                    "allowedClients": [original_client_id],
                }
            }
            update_request = {
                "gatewayIdentifier": gateway_id,
                "name": gateway["name"],
                "roleArn": gateway["roleArn"],
                "protocolType": gateway["protocolType"],
                "authorizerType": gateway["authorizerType"],
                "authorizerConfiguration": restored_auth,
            }
            for field in [
                "description", "protocolConfiguration", "kmsKeyArn",
                "customTransformConfiguration", "interceptorConfigurations",
                "exceptionLevel",
            ]:
                if field in gateway:
                    update_request[field] = gateway[field]
            # Omit policyEngineConfiguration (already detached in step 1)
            control_client.update_gateway(**update_request)
            print("Gateway allowedClients restored")
        except Exception as e:
            print(f"Warning: Failed to restore allowedClients: {e}")

    # Step 3: Delete all policies, then the policy engine
    policy_engine = config.get("policy_engine", {})
    engine_id = policy_engine.get("id")
    if engine_id:
        print(f"Cleaning up policy engine {engine_id}...")
        try:
            policy_client = PolicyClient(region_name=region)
            policy_client.cleanup_policy_engine(engine_id)
            print("Policy engine cleaned up")
        except Exception as e:
            print(f"Warning: Failed to cleanup policy engine: {e}")

    # Step 4: Delete Cognito app clients
    user_pool_id = cognito_clients.get("user_pool_id")
    if user_pool_id:
        cognito = boto3.client("cognito-idp", region_name=region)
        for role in ["manager", "developer"]:
            client_id = cognito_clients.get(role, {}).get("client_id")
            if client_id:
                print(f"Deleting {role} app client: {client_id}")
                try:
                    cognito.delete_user_pool_client(
                        UserPoolId=user_pool_id, ClientId=client_id
                    )
                    print(f"{role.capitalize()} client deleted")
                except Exception as e:
                    print(f"Warning: Failed to delete {role} client: {e}")

        # Step 5: Delete Cognito resource server
        rs_id = cognito_clients.get("resource_server_identifier")
        if rs_id:
            print(f"Deleting resource server: {rs_id}")
            try:
                cognito.delete_resource_server(
                    UserPoolId=user_pool_id, Identifier=rs_id
                )
                print("Resource server deleted")
            except Exception as e:
                print(f"Warning: Failed to delete resource server: {e}")

    # Step 6: Remove config file
    print("Removing policy_config.json")
    os.remove(POLICY_CONFIG_FILE)
    print("Cleanup complete")


if __name__ == "__main__":
    clean_resources()
