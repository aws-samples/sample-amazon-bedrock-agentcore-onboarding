import json
import os
from pathlib import Path

import boto3


def clean_resources():
    """Clean up all resources created by 09_browser_use (Browser Use)."""
    # TODO: Define the config file name if this workshop generates one
    # config_file = Path("browser_use_config.json")

    region = boto3.Session().region_name
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    # TODO: Read config and delete resources in dependency order
    # Example:
    #   with config_file.open("r", encoding="utf-8") as f:
    #       config = json.load(f)
    #   client.delete_...(...)

    print("TODO: implement resource cleanup for Browser Use")

    # TODO: Remove generated config files
    # os.remove(config_file)


if __name__ == "__main__":
    clean_resources()
