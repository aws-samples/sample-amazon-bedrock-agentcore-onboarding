# AgentCore Memory Integration

[English](README.md) / [日本語](README_ja.md)

This implementation demonstrates **AgentCore Memory** capabilities through a cost estimation agent that uses both short-term and long-term memory. The demo integrates the same `AWSCostEstimatorAgent` from Lab 01 (Code Interpreter + MCP pricing) with AgentCore Memory for a real end-to-end workflow.

## Process Overview

```mermaid
sequenceDiagram
    participant User as User
    participant Agent as AgentWithMemory
    participant Estimator as Cost Estimator
    participant Memory as AgentCore Memory
    participant Bedrock as Amazon Bedrock

    Note over User,Memory: Step 1: Store estimates (short-term memory)
    User->>Agent: estimate("t3.micro + EBS")
    Agent->>Estimator: AWSCostEstimatorAgent
    Estimator-->>Agent: Cost results
    Agent->>Memory: create_event() → SHORT-TERM MEMORY
    Memory-->>Agent: Event stored
    Agent-->>User: Cost estimate

    Note over User,Memory: Step 2: Compare using short-term memory
    User->>Agent: compare("my estimates")
    Agent->>Memory: list_events() → SHORT-TERM MEMORY
    Memory-->>Agent: Historical estimates
    Agent->>Bedrock: Generate comparison
    Bedrock-->>Agent: Comparison analysis
    Agent-->>User: Side-by-side comparison

    Note over User,Memory: Step 3: Propose using long-term memory
    User->>Agent: propose("best architecture")
    Agent->>Memory: retrieve_memories() → LONG-TERM MEMORY
    Memory-->>Agent: User preferences
    Agent->>Bedrock: Generate proposal
    Bedrock-->>Agent: Personalized recommendation
    Agent-->>User: Architecture proposal
```

## Prerequisites

1. **Cost Estimator deployed** - Complete `01_code_interpreter` setup first
2. **AWS credentials** - With `bedrock-agentcore-control` and `bedrock:InvokeModel` permissions
3. **Dependencies** - Installed via `uv` (see pyproject.toml)

## How to use

### File Structure

```
03_memory/
├── README.md                      # This documentation
└── test_memory.py                 # Main implementation and test suite
```

### Step 1: Run the Demo

```bash
cd 03_memory
uv run python test_memory.py
```

This runs 3 steps sequentially:
1. **Estimate** x2 — generates cost estimates using `AWSCostEstimatorAgent`, stores as short-term memory events via `create_event()`
2. **Compare** — retrieves events via `list_events()` and generates comparison
3. **Propose** — retrieves extracted preferences via `retrieve_memories()` for personalized recommendation

On first run, memory creation takes ~3 minutes. Subsequent runs reuse existing memory (instant).

### Step 2: Force Recreation (Clean Start)

```bash
cd 03_memory
uv run python test_memory.py --force
```

Deletes existing memory and creates a fresh instance. Use this for a clean start.

## Key Implementation Patterns

### Memory-Enhanced Agent

```python
class AgentWithMemory:
    def __init__(self, actor_id: str, region: str = "us-west-2", force_recreate: bool = False):
        # Initialize AgentCore Memory with user preference strategy
        self.memory = self.memory_client.create_memory_and_wait(
            name="cost_estimator_memory",
            strategies=[{
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreferenceExtractor",
                    "description": "Extracts user preferences for AWS architecture decisions",
                    # {actorId} is a literal template variable — the service resolves it
                    # per create_event(), isolating each user under their own namespace.
                    "namespaceTemplates": ["/actor/{actorId}/preferences/"]
                }
            }],
            event_expiry_days=7,
        )
```

### Context Manager Pattern

```python
memory_agent = AgentWithMemory(actor_id="user123")
with memory_agent as agent:
    # Step 1-2: Estimate and compare (short-term memory)
    agent("estimate: t3.nano")
    agent("estimate: t3.micro + EBS")
    agent("compare my estimates")

    # Step 3: Propose using long-term memory (retrieve_memories)
    agent("propose best architecture")
```

### Memory Storage Pattern

```python
@tool
def estimate(self, architecture_description: str) -> str:
    # Use the Cost Estimator Agent (Code Interpreter + MCP pricing)
    cost_estimator = AWSCostEstimatorAgent(region=self.region)
    result = cost_estimator.estimate_costs(architecture_description)

    # Store interaction → triggers async preference extraction
    self.memory_client.create_event(
        memory_id=self.memory_id,
        actor_id=self.actor_id,
        session_id=self.session_id,
        messages=[
            (architecture_description, "USER"),
            (result, "ASSISTANT")
        ]
    )
    return result
```

## Memory Types Demonstrated

### Short-term Memory (Session Context)
- **API**: `create_event()` to store, `list_events()` to retrieve
- **Purpose**: Store multiple estimates within a session for immediate comparison
- **Use Case**: Compare different EC2 instance types side-by-side

### Long-term Memory (User Preferences)
- **API**: `retrieve_memories()` to retrieve extracted preferences
- **Purpose**: Learn user decision patterns and preferences over time
- **Note**: Extraction is **asynchronous** ([AWS docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html))
- **Use Case**: Recommend architectures based on historical choices

#### Namespace: define with `{actorId}`, retrieve with the resolved value

A namespace organizes long-term memories and isolates them per actor. The template is written once and resolved by the service at write time, so the two sides are asymmetric:

| Process | Code | Who resolves `{actorId}` |
|---------|------|--------------------------|
| **Define** (`create_memory`) | `namespaceTemplates=["/actor/{actorId}/preferences/"]` | Literal placeholder — the **service** resolves it per `create_event()` |
| **Retrieve** (`retrieve_memories`) | `namespace=f"/actor/{self.actor_id}/preferences/"` | **You** resolve it; it must match the stored path |

```
create_memory   "/actor/{actorId}/preferences/"      ← literal template
create_event    actor_id="user123"
              → stored at "/actor/user123/preferences/"   ← service resolves
retrieve        f"/actor/{self.actor_id}/preferences/"
              → "/actor/user123/preferences/"             ← must match
```

Because both sides derive from the same `actor_id`, they cannot drift. Use actor-first ordering (`/actor/{actorId}/...`) so each user's data stays isolated and IAM can scope access per user with `namespacePath=/actor/${aws:PrincipalTag/userId}/*`. Do **not** f-string the template at definition time — that bakes one actor in and defeats per-user isolation. See [namespace design patterns](https://aws.amazon.com/blogs/machine-learning/organizing-agents-memory-at-scale-namespace-design-patterns-in-agentcore-memory/) and [specify long-term memory organization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html).

## Usage Examples

### Full Example

```python
from test_memory import AgentWithMemory

memory_agent = AgentWithMemory(actor_id="user123")
with memory_agent as agent:
    # Generate estimates (stored as short-term memory events)
    agent("estimate: 1 EC2 t3.nano instance")
    agent("estimate: 1 EC2 t3.micro with 20GB gp3 EBS")

    # Compare using short-term memory (list_events)
    agent("compare my recent estimates")

    # Get personalized recommendation using long-term memory (retrieve_memories)
    agent("propose optimal architecture for my needs")
```

## Memory Benefits

- **Session Continuity** - Compare multiple estimates within the same session
- **Learning Capability** - Agent learns user preferences over time
- **Personalized Recommendations** - Proposals based on historical patterns
- **Cost Optimization** - Memory reuse reduces initialization time
- **Debugging Support** - Event inspection for troubleshooting

## References

- [AgentCore Memory Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
- [Memory Strategies Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [Amazon Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Strands Agents Documentation](https://github.com/aws-samples/strands-agents)

---

**Next Steps**: Integrate memory-enhanced agents into your applications to provide personalized, context-aware user experiences.
