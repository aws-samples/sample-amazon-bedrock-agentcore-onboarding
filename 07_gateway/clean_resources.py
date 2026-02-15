import json
import os
from pathlib import Path
import boto3


def clean_resources():
    """Clean up all resources created by the identity setup"""
    config_file = Path("outbound_gateway.json")

    with config_file.open("r", encoding="utf-8") as f:
        config = json.load(f)

    region = boto3.Session().region_name
    gateway_client = boto3.client('bedrock-agentcore-control', region_name=region)

    gateway_id = config["gateway"]["id"]

    print(f"Deleting all targets for gateway {gateway_id}.")
    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gateway_id,
        maxResults=100
    )
    for item in list_response['items']:
        target_id = item["targetId"]
        print(f"Deleting target {target_id}.")
        gateway_client.delete_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
    print(f"Deleting gateway {gateway_id}.")
    gateway_client.delete_gateway(gatewayIdentifier=gateway_id)

    os.remove(".agentcore.yaml")
    os.remove("outbound_gateway.json")


if __name__ == "__main__":
    clean_resources()
