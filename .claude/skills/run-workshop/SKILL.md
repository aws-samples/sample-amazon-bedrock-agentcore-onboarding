---
name: run-workshop
description: Run the AgentCore workshop steps sequentially to test the full attendee experience. Use when someone wants to execute, test, or run through the workshop.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList, AskUserQuestion
---

# Run Workshop

Execute AgentCore onboarding workshop steps sequentially, simulating the full attendee experience.

## Usage

- `/run-workshop` — Run all available steps (01 through 07)
- `/run-workshop 01` — Run only step 01
- `/run-workshop 01 03` — Run steps 01 and 03
- `/run-workshop 01-05` — Run steps 01 through 05

## Arguments

`$ARGUMENTS` contains step numbers or ranges to run (e.g., `01 03` or `01-05`).
If empty, run ALL available steps in order.

## Available Steps

| Step | Directory | Action | Command |
|------|-----------|--------|---------|
| 01 | `01_code_interpreter/` | Test cost estimator agent locally | `cd <root>/01_code_interpreter && uv run python test_cost_estimator_agent.py` |
| 02 | `02_runtime/` | Prepare and deploy agent to runtime | See multi-step below |
| 03 | `03_memory/` | Test agent with memory integration | `cd <root>/03_memory && uv run python test_memory.py` |
| 04 | `04_observability/` | Test observability with CloudWatch | `cd <root>/04_observability && uv run python test_observability.py` |
| 05 | `05_evaluation/` | (Coming soon - skip) | N/A |
| 06 | `06_identity/` | Setup and test identity/OAuth2 | See multi-step below |
| 07 | `07_gateway/` | Deploy Lambda, setup and test gateway | See multi-step below |
| 08 | `08_policy/` | (Coming soon - skip) | N/A |
| 09 | `09_browser_use/` | (Coming soon - skip) | N/A |

## Multi-Step Details

### Step 02 - Runtime
```bash
# 1. Prepare agent
cd <root>/02_runtime && uv run python prepare_agent.py --source-dir ../01_code_interpreter/cost_estimator_agent

# 2. Configure runtime (uses agentcore CLI)
uv run agentcore configure --entrypoint deployment/invoke.py --name cost_estimator_agent --execution-role <role_arn> --requirements-file deployment/requirements.txt

# 3. Launch runtime
uv run agentcore launch

# 4. Test invocation
uv run agentcore invoke '{"prompt": "I would like to connect t3.micro from my PC. How much does it cost?"}'
```
Note: `prepare_agent.py` outputs the exact configure command. Parse its output to get the correct role ARN and command.

### Step 06 - Identity
```bash
# 1. Setup OAuth2 credential provider
cd <root>/06_identity && uv run python setup_inbound_authorizer.py

# 2. Test identity-protected agent
uv run python test_identity_agent.py
```
Prerequisite: Step 02 must be completed (needs `.bedrock_agentcore.yaml`).

### Step 07 - Gateway
```bash
# 1. Deploy Lambda function (requires SES sender email)
cd <root>/07_gateway && bash deploy.sh <ses-sender-email>

# 2. Setup gateway
uv run python setup_outbound_gateway.py

# 3. Test gateway
uv run python test_gateway.py
```
Prerequisite: Step 06 must be completed (needs `inbound_authorizer.json`).

## Dependencies Between Steps

```
01 (standalone)
02 (depends on 01's agent code)
03 (depends on 01's agent code)
04 (depends on 02's deployed runtime)
06 (depends on 02's deployed runtime)
07 (depends on 06's identity setup)
```

## Implementation

1. Parse `$ARGUMENTS`:
   - If empty, use all steps: `01 02 03 04 06 07` (skip 05, 08, 09 as coming soon)
   - If ranges like `01-05`, expand to individual steps
   - Sort in ascending order
2. Validate dependencies:
   - If step 04 is requested, ensure 02 is included or already completed
   - If step 06 is requested, ensure 02 is included or already completed
   - If step 07 is requested, ensure 06 is included or already completed
3. Create a task list tracking each step
4. For each step (in order):
   a. Mark task as in_progress
   b. Execute the step's commands from the correct working directory
   c. For multi-step steps (02, 06, 07), execute each sub-step sequentially
   d. For step 07, ask the user for their SES sender email before deploying
   e. Capture and display output
   f. If a step fails, ask the user whether to continue or stop
   g. Mark task as completed
5. Print a final summary with pass/fail status for each step

## Important Notes

- All Python commands use `uv run` prefix
- Scripts use relative paths, so `cd` to the step directory before running
- Step 02 involves interactive `agentcore` CLI commands that may take several minutes
- Step 06's OIDC endpoint can take 5+ minutes to become available
- Steps 05, 08, 09 are placeholders (coming soon) - skip with a note
- Timeouts: allow up to 10 minutes for runtime deployment and OIDC waits
