import json
import os
from pathlib import Path
import boto3


def clean_resources():
    """Clean up all resources created by the identity setup"""
    config_file = Path("inbound_authorizer.json")

    with config_file.open("r", encoding="utf-8") as f:
        config = json.load(f)

    region = boto3.Session().region_name
    
    # Clean up AgentCore OAuth2 credential provider
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    provider_name = config["provider"]["name"]
    print(f"Deleting OAuth2 credential provider: {provider_name}")
    client.delete_oauth2_credential_provider(name=provider_name)
    print(f"OAuth2 credential provider {provider_name} deleted successfully")

    # Clean up Cognito resources
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
    else:
        print("No domain found for user pool")

    # Disable deletion protection and delete user pool
    print(f"Disabling deletion protection for user pool: {user_pool_id}")
    cognito_client.update_user_pool(
        UserPoolId=user_pool_id,
        DeletionProtection="INACTIVE"
    )

    print(f"Deleting user pool: {user_pool_id}")
    cognito_client.delete_user_pool(UserPoolId=user_pool_id)
    print(f"User pool {user_pool_id} deleted successfully")

    runtime_id = config["runtime"]["id"]
    runtime_delete_response = client.delete_agent_runtime(
        agentRuntimeId=runtime_id
    )

    os.remove(".agentcore.yaml")
    os.remove("inbound_authorizer.json")


if __name__ == "__main__":
    clean_resources()
