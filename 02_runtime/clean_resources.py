import boto3
import yaml
import os
import time


def clean_resources():
    config_path = ".bedrock_agentcore.yaml"
    if not os.path.exists(config_path):
        print("No .bedrock_agentcore.yaml found, nothing to clean.")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    agent_name = config.get("default_agent")
    agent_config = config.get("agents", {}).get(agent_name, {})
    agent_id = agent_config.get("bedrock_agentcore", {}).get("agent_id")
    ecr_id = agent_config.get("aws", {}).get("ecr_repository")
    region = agent_config.get("aws", {}).get("region") or boto3.Session().region_name

    agentcore_control_client = boto3.client(
        'bedrock-agentcore-control',
        region_name=region
    )

    # Delete agent runtime
    if agent_id:
        try:
            print(f"Deleting runtime: {agent_id}")
            agentcore_control_client.delete_agent_runtime(agentRuntimeId=agent_id)
            print(f"Runtime {agent_id} deleted successfully")
        except agentcore_control_client.exceptions.ResourceNotFoundException:
            print(f"Runtime {agent_id} not found (already deleted)")
        except Exception as e:
            print(f"Warning: Failed to delete runtime {agent_id}: {e}")
    else:
        print("No agent_id found, skipping runtime deletion")

    # Delete ECR repository (only for container deploy)
    if ecr_id:
        try:
            ecr_client = boto3.client('ecr', region_name=region)
            print(f"Deleting ECR: {ecr_id}")
            ecr_client.delete_repository(
                repositoryName=ecr_id.split('/')[-1],
                force=True
            )
            print(f"ECR {ecr_id} deleted successfully")
        except Exception as e:
            print(f"Warning: Failed to delete ECR {ecr_id}: {e}")
    else:
        print("No ECR repository configured (Direct Code Deploy), skipping")

    # Clean up configuration files
    print("Deleting configuration files")
    for f in [".bedrock_agentcore.yaml", "Dockerfile"]:
        if os.path.exists(f):
            os.remove(f)
            print(f"  Removed {f}")


if __name__ == "__main__":
    clean_resources()
