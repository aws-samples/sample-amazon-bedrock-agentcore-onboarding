---
name: run-workshop
description: Run the AgentCore workshop steps sequentially to test the full attendee experience. Use when someone wants to execute, test, or run through the workshop.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList, AskUserQuestion
---

# Run Workshop

Execute AgentCore onboarding workshop steps sequentially, simulating the full attendee experience.

The workshop uses the **AgentCore CLI** (`npm install -g @aws/agentcore`). Agents are created
with `agentcore create`, the code is placed by `agents/setup.py`, and everything is created in
AWS with `agentcore deploy`.

## Usage

- `/run-workshop` — Run all steps (01 through 09)
- `/run-workshop 01` — Run only step 01
- `/run-workshop 01 03` — Run steps 01 and 03
- `/run-workshop 01-05` — Run steps 01 through 05

## Arguments

`$ARGUMENTS` contains step numbers or ranges to run (e.g., `01 03` or `01-05`).
If empty, run ALL steps in order.

## Project Naming Convention

Each step creates an AgentCore project under `agents/`. All are gitignored (`My*Agent/`).

| Project | Created by | Used by |
|---------|-----------|---------|
| `agents/MyCostEstimatorAgent` | Step 01 (deleted at the end of 01), recreated in Step 02 | 02, 04, 05 |
| `agents/MyCostEstimatorAgent` | Step 02 | 03 (memory added) |
| `agents/MyCostEstimatorAgent` | Step 02 | 02, 03, 04, 05, 06 (06 adds two more runtimes: agent + MCP server) |
| `agents/MyGatewayProject` | Step 07 (`--no-agent`) | 07, 08 |

## Available Steps

| Step | Directory | Action |
|------|-----------|--------|
| 01 | `agents/` | Scaffold, run locally with `agentcore dev`, then delete the scaffold |
| 02 | `agents/`, `02_runtime/` | Deploy the base agent, invoke via CLI and boto3 |
| 03 | `agents/`, `03_memory/` | Deploy with memory (overlay), verify short/long-term memory |
| 04 | `04_observability/` | Generate traces, inspect with `agentcore traces` / `logs` |
| 05 | `05_evaluation/`, `agents/` | Local eval, then `agentcore run eval` / `add online-eval` |
| 06 | `06_identity/`, `agents/` | Cognito + CUSTOM_JWT runtime + credential provider |
| 07 | `07_gateway/`, `agents/` | SAM Lambda + `agentcore add gateway` / `add gateway-target` |
| 08 | `08_policy/`, `agents/` | `agentcore add policy-engine` / `add policy` (Cedar) |
| 09 | `09_browser_use/` | Browser automation (no CLI resources) |

## Step Details

### Step 01 - Code Interpreter
```bash
cd <root>/agents
agentcore create --name MyCostEstimatorAgent --framework Strands \
    --model-provider Bedrock --protocol HTTP --build CodeZip --memory none --skip-git
python setup.py --target MyCostEstimatorAgent
cd MyCostEstimatorAgent/app/MyCostEstimatorAgent && uv sync && cd ../..
agentcore dev          # interactive — opens the agent inspector; Ctrl+C to stop
cd .. && rm -rf MyCostEstimatorAgent
```
Note: `agentcore dev` is interactive. When automating, skip it or run
`agentcore dev "<prompt>"` in a second shell against the running server.

### Step 02 - Runtime
```bash
cd <root>/agents
agentcore create --name MyCostEstimatorAgent --framework Strands \
    --model-provider Bedrock --protocol HTTP --build CodeZip --memory none --skip-git
python setup.py --target MyCostEstimatorAgent
cd MyCostEstimatorAgent/app/MyCostEstimatorAgent && uv sync && cd ../..
agentcore deploy -y
agentcore status
agentcore invoke 'I would like to connect t3.micro from my PC. How much does it cost?'

cd <root>/02_runtime
uv run python invoke_agent.py --agent-arn <runtime-arn>
uv run python invoke_agent.py --agent-arn <runtime-arn> --demo-session
```

### Step 03 - Memory
```bash
cd <root>/agents/MyCostEstimatorAgent
agentcore add memory --name MyCostEstimatorAgentMemory \
    --strategies SEMANTIC,USER_PREFERENCE,SUMMARIZATION,EPISODIC
cd .. && python setup.py --target MyCostEstimatorAgent --overlay ../03_memory/agent
cd MyCostEstimatorAgent/app/MyCostEstimatorAgent && uv sync && cd ../..
agentcore deploy -y
agentcore status        # note the Runtime ARN and Memory ID

cd <root>/03_memory
uv run python test_memory.py --agent-arn <runtime-arn> --memory-id <memory-id>
```
Note: long-term extraction is asynchronous; the script polls for up to `--wait` seconds (300).

### Step 04 - Observability
```bash
cd <root>/04_observability
uv run python test_observability.py --project-dir ../agents/MyCostEstimatorAgent

cd <root>/agents/MyCostEstimatorAgent
agentcore traces list --since 30m
agentcore logs --since 30m --query "Invoking Cost Estimator"
```
Prerequisite: Step 02's `MyCostEstimatorAgent` must be deployed.

### Step 05 - Evaluation
```bash
# Local evaluation
cd <root>/05_evaluation
uv run python test_evaluation.py --case single-ec2

# On-demand / online evaluation on the deployed agent
cd <root>/agents/MyCostEstimatorAgent
agentcore add evaluator --name cost_estimator_tool_usage --level TRACE \
    --config ../../05_evaluation/evaluators/tool_usage_evaluator.json
agentcore deploy -y
agentcore run eval --runtime MyCostEstimatorAgent \
    --evaluator cost_estimator_tool_usage Builtin.Correctness --days 1
agentcore evals history

agentcore add online-eval --name cost_estimator_online_eval \
    --runtime MyCostEstimatorAgent \
    --evaluator cost_estimator_tool_usage Builtin.Correctness \
    --sampling-rate 100 --enable-on-create
agentcore deploy -y
```
Prerequisites: Step 02 deployed, Step 04 run (traces must exist; they take 5–10 min to appear).
Cleanup order matters: remove `online-eval` before `evaluator`.

### Step 06 - Identity
```bash
# 1. Cognito (outside the CLI's scope)
cd <root>/06_identity && uv run python setup_cognito.py

# 2. Two JWT-protected runtimes + the credential provider
cd <root>/agents/MyCostEstimatorAgent   # Lab 2's project; a project can hold several agents
# inbound: the agent runtime
agentcore add agent --name MySecureAgent --language Python --framework Strands \
    --model-provider Bedrock --memory none \
    --authorizer-type CUSTOM_JWT --discovery-url <url> --allowed-clients <client-id>
# the callee: an MCP server, also JWT protected
agentcore add agent --name MyMcpServer --language Python --protocol MCP --build CodeZip \
    --memory none \
    --authorizer-type CUSTOM_JWT --discovery-url <url> --allowed-clients <client-id>
# outbound: the credential provider the agent uses to reach the MCP server
agentcore add credential --name CostEstimatorOutboundIdentity --type oauth \
    --discovery-url <url> --client-id <id> --client-secret <secret> --scopes agentcore/invoke

# 3. Agent code (overlay) and the first deploy
cd .. && python setup.py --target MyCostEstimatorAgent --agent MySecureAgent \
    --overlay ../06_identity/agent
# setup.py also drops credential declarations left unused by the MCP agent
cd MyCostEstimatorAgent
for d in MySecureAgent MyMcpServer; do (cd app/$d && uv sync); done
agentcore deploy -y

# 4. Pass the MCP runtime ARN via envVars, then deploy again
python - <<'PY'
import json
from pathlib import Path
state = json.load(open("agentcore/.cli/deployed-state.json"))
arn = next(iter(state["targets"].values()))["resources"]["runtimes"]["MyMcpServer"]["runtimeArn"]
path = Path("agentcore/agentcore.json")
config = json.load(path.open())
for runtime in config["runtimes"]:
    if runtime["name"] == "MySecureAgent":
        runtime["envVars"] = [{"name": "MCP_RUNTIME_ARN", "value": arn}]
path.write_text(json.dumps(config, indent=2) + "\n")
PY
agentcore deploy -y

# 5. Verify inbound denial/allow and the outbound token
cd <root>/06_identity && uv run python test_identity_agent.py
cd <root>/agents/MyCostEstimatorAgent
agentcore logs --runtime MySecureAgent --since 10m | grep -E 'GetResourceOauth2Token|MCP call'
```
Note: the Cognito domain can take several minutes to resolve; `setup_cognito.py` waits for it.
`setup_cognito.py` prints the exact `add agent` / `add credential` commands with real values.
`agentcore logs` needs `--runtime` because this project holds three runtimes.
Clean up with `remove agent --name MySecureAgent` / `--name MyMcpServer` — `remove all` would
also drop Lab 2's agent.

### Step 07 - Gateway
```bash
# 1. Lambda via SAM (requires SES sender email)
cd <root>/07_gateway && bash deploy.sh <ses-sender-email>

# 2. Gateway + target + credential
cd <root>/agents
agentcore create --name MyGatewayProject --no-agent --skip-git
cd MyGatewayProject
agentcore add gateway --name AWSCostEstimatorGateway --protocol-type MCP \
    --authorizer-type CUSTOM_JWT --discovery-url <url> --allowed-clients <client-id>
agentcore add gateway-target --name AWSCostEstimatorGatewayTarget \
    --gateway AWSCostEstimatorGateway --type lambda-function-arn \
    --lambda-arn <lambda-arn> --tool-schema-file ../../07_gateway/tool_schema.json
agentcore add credential --name CostEstimatorOutboundIdentity --type oauth \
    --discovery-url <url> --client-id <id> --client-secret <secret> --scopes agentcore/invoke
agentcore deploy -y

# 3. Test
cd <root>/07_gateway
uv run python test_gateway.py --list-tools
uv run python test_gateway.py --address <ses-sender-email>
```
Prerequisite: Step 06's Cognito (`06_identity/inbound_authorizer.json`).
Do NOT pass `--no-semantic-search` — CloudFormation only accepts `SEMANTIC`.
`deploy.sh` prints the exact commands with the real Lambda ARN.

### Step 08 - Policy
```bash
# 1. Render the Cedar policy and add the demo scopes
cd <root>/08_policy && uv run python setup_policy_demo.py

# 2. Policy engine + policy
cd <root>/agents/MyGatewayProject
agentcore add policy-engine --name cost_estimator_policy_engine \
    --attach-to-gateways AWSCostEstimatorGateway --attach-mode ENFORCE
agentcore add policy --name email_scope_policy --engine cost_estimator_policy_engine \
    --source ../../08_policy/policies/email_scope.cedar
agentcore deploy -y

# 3. Compare manager vs viewer
cd <root>/08_policy && uv run python test_policy.py
```
Prerequisite: Step 07's Gateway must be deployed (the Cedar policy needs its ARN).

### Step 09 - Browser Use
```bash
cd <root>/09_browser_use
uv run python test_browser_use.py --architecture "2 EC2 t3.micro 24/7, RDS MySQL db.micro"
uv run python clean_resources.py
```
Note: AgentCore Browser is not managed by the CLI — no `agentcore create` / `deploy` needed.

## Dependencies Between Steps

```
01 (standalone — deletes its scaffold at the end)
02 (recreates MyCostEstimatorAgent and deploys it)
03 (adds memory to MyCostEstimatorAgent)
04 (depends on 02's deployed runtime)
05 (depends on 02's runtime and 04's traces)
06 (standalone project MySecureAgent + Cognito)
07 (depends on 06's Cognito)
08 (depends on 07's Gateway)
09 (standalone)
```

## Implementation

1. Parse `$ARGUMENTS`:
   - If empty, use all steps: `01 02 03 04 05 06 07 08 09`
   - If ranges like `01-05`, expand to individual steps
   - Sort in ascending order
2. Validate dependencies:
   - 04 / 05 require 02 to be included or already deployed
   - 05 also needs traces from 04 (wait 5–10 minutes after 04)
   - 07 requires 06 to be included or already completed
   - 08 requires 07 to be included or already completed
3. Create a task list tracking each step
4. For each step (in order):
   a. Mark task as in_progress
   b. Execute the step's commands from the correct working directory
   c. Parse setup script output (`setup_cognito.py`, `deploy.sh`) for real ARNs / IDs
   d. For step 07, ask the user for their SES sender email before deploying
   e. Capture and display output
   f. If a step fails, ask the user whether to continue or stop
   g. Mark task as completed
5. Print a final summary with pass/fail status for each step

## Important Notes

- All Python commands use `uv run` prefix; AgentCore CLI commands do not
- Scripts use relative paths, so `cd` to the step directory before running
- `agentcore deploy` takes several minutes; pass `-y` to skip the confirmation prompt
- `runtimeSessionId` must be at least 33 characters
- Step 01's `agentcore dev` is interactive — skip it when running unattended
- Step 06's OIDC endpoint can take 5+ minutes to become available
- Traces take 5–10 minutes to become available for `agentcore run eval`
- If a deploy fails, the stack may be stuck in `REVIEW_IN_PROGRESS`; delete it with
  `aws cloudformation delete-stack --stack-name AgentCore-<project>-default`
- Timeouts: allow up to 10 minutes for deployments and OIDC waits
