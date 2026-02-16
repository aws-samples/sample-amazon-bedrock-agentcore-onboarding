import json
import os
import time
from pathlib import Path
import boto3


def clean_resources():
    """Clean up all resources created by the gateway setup"""
    config_file = Path("outbound_gateway.json")

    if not config_file.exists():
        print("No outbound_gateway.json found, nothing to clean.")
        return

    with config_file.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if "gateway" not in config:
        print("No gateway config found, cleaning up files only.")
        _cleanup_files()
        return

    region = boto3.Session().region_name
    gateway_client = boto3.client('bedrock-agentcore-control', region_name=region)
    gateway_id = config["gateway"]["id"]

    # Delete all targets first
    try:
        print(f"Deleting all targets for gateway {gateway_id}.")
        list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier=gateway_id,
            maxResults=100
        )
        for item in list_response.get('items', []):
            target_id = item["targetId"]
            print(f"Deleting target {target_id}.")
            gateway_client.delete_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id
            )
    except Exception as e:
        print(f"Warning: Failed to delete targets: {e}")

    # Delete gateway with retry (target deletion may take time to propagate)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Deleting gateway {gateway_id} (attempt {attempt}/{max_retries}).")
            gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
            print(f"Gateway {gateway_id} deleted successfully")
            break
        except gateway_client.exceptions.ValidationException as e:
            if "has targets associated" in str(e) and attempt < max_retries:
                print("Targets still propagating, waiting 5s...")
                time.sleep(5)
            else:
                print(f"Warning: Failed to delete gateway: {e}")
                break
        except gateway_client.exceptions.ResourceNotFoundException:
            print(f"Gateway {gateway_id} not found (already deleted)")
            break
        except Exception as e:
            print(f"Warning: Failed to delete gateway: {e}")
            break

    _cleanup_files()


def _cleanup_files():
    """Remove configuration files"""
    for f in ["outbound_gateway.json", ".agentcore.yaml", ".agentcore.json"]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Removed {f}")


if __name__ == "__main__":
    clean_resources()
