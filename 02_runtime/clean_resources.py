import boto3
import yaml
import os


def clean_resources():
    """AgentCoreランタイムとECRリポジトリを削除してリソースをクリーンアップ"""
    with open(".bedrock_agentcore.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    agent_name = config.get("default_agent")
    agent_id = config.get("agents").get(agent_name).get("bedrock_agentcore").get("agent_id")
    ecr_id = config.get("agents").get(agent_name).get("aws").get("ecr_repository")

    if not agent_id or not ecr_id:
        raise ValueError("agent_id or ecr_id not found in .bedrock_agentcore.yaml")

    region = boto3.Session().region_name

    agentcore_control_client = boto3.client(
        'bedrock-agentcore-control',
        region_name=region
    )
    ecr_client = boto3.client(
        'ecr',
        region_name=region
    )

    print(f"Deleting runtime: {agent_id}")
    runtime_delete_response = agentcore_control_client.delete_agent_runtime(
        agentRuntimeId=agent_id            
    )

    print(f"Deleting ECR: {ecr_id}")
    response = ecr_client.delete_repository(
        repositoryName=ecr_id.split('/')[-1],
        force=True
    )

    print(f"Deleting configuration files")
    os.remove(".bedrock_agentcore.yaml")
    os.remove("Dockerfile")


if __name__ == "__main__":
    clean_resources()
