import boto3
from bedrock_agentcore.memory import MemoryClient


def clean_resources():
    region = boto3.Session().region_name
    client = MemoryClient(region_name=region)
    for memory in client.list_memories():
        memory_id = memory.get("id")
        if memory_id.startswith("cost_estimator_memory"):
            print(f"Delete {memory_id}.")
            client.delete_memory_and_wait(memory_id)


if __name__ == "__main__":
    clean_resources()
