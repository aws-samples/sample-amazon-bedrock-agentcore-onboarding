import json
import os
from pathlib import Path
import boto3


def clean_resources():
    """Clean up all resources created by the identity setup"""
    config_file = Path("inbound_authorizer.json")

    if not config_file.exists():
        print("No inbound_authorizer.json found, nothing to clean.")
        return

    with config_file.open("r", encoding="utf-8") as f:
        config = json.load(f)

    region = boto3.Session().region_name

    # Clean up AgentCore OAuth2 credential provider
    if "provider" in config:
        try:
            client = boto3.client("bedrock-agentcore-control", region_name=region)
            provider_name = config["provider"]["name"]
            print(f"Deleting OAuth2 credential provider: {provider_name}")
            client.delete_oauth2_credential_provider(name=provider_name)
            print(f"OAuth2 credential provider {provider_name} deleted successfully")
        except Exception as e:
            print(f"Warning: Failed to delete OAuth2 provider: {e}")

    # Clean up Cognito resources
    if "cognito" in config:
        try:
            cognito_client = boto3.client("cognito-idp", region_name=region)
            user_pool_id = config["cognito"]["user_pool_id"]
            client_id = config["cognito"]["client_id"]

            # Delete user pool client
            print(f"Deleting user pool client: {client_id}")
            cognito_client.delete_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            print(f"User pool client {client_id} deleted successfully")

            user_pool_details = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            domain = user_pool_details.get("UserPool", {}).get("Domain")

            if domain:
                print(f"Deleting user pool domain: {domain}")
                cognito_client.delete_user_pool_domain(Domain=domain, UserPoolId=user_pool_id)
                print(f"Domain {domain} deleted successfully")

            # Disable deletion protection and delete user pool
            print(f"Disabling deletion protection for user pool: {user_pool_id}")
            cognito_client.update_user_pool(
                UserPoolId=user_pool_id,
                DeletionProtection="INACTIVE"
            )

            print(f"Deleting user pool: {user_pool_id}")
            cognito_client.delete_user_pool(UserPoolId=user_pool_id)
            print(f"User pool {user_pool_id} deleted successfully")
        except Exception as e:
            print(f"Warning: Failed to clean up Cognito resources: {e}")

    # Clean up identity runtime (may not exist if setup failed before runtime creation)
    if "runtime" in config:
        try:
            client = boto3.client("bedrock-agentcore-control", region_name=region)
            runtime_id = config["runtime"]["id"]
            print(f"Deleting identity runtime: {runtime_id}")
            client.delete_agent_runtime(agentRuntimeId=runtime_id)
            print(f"Runtime {runtime_id} deleted successfully")
        except Exception as e:
            print(f"Warning: Failed to delete runtime: {e}")
    else:
        print("No runtime in config (was never created), skipping")

    # Clean up configuration files
    for f in ["inbound_authorizer.json", ".agentcore.yaml"]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Removed {f}")


if __name__ == "__main__":
    clean_resources()
