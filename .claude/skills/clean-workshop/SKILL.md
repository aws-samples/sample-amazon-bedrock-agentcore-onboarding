---
name: clean-workshop
description: Clean up AWS resources created by the AgentCore workshop. Use when someone wants to tear down, clean up, or remove workshop resources.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList
---

# Clean Workshop Resources

Clean up AWS resources created by the AgentCore onboarding workshop.

## Usage

- `/clean-workshop` — Clean all workshop resources (09, 08, 07, 06, 05, 03, 02)
- `/clean-workshop 02` — Clean only step 02 (runtime)
- `/clean-workshop 02 03` — Clean steps 02 and 03
- `/clean-workshop 05 06 07` — Clean steps 05, 06, and 07
- `/clean-workshop 08 09` — Clean steps 08 and 09

## Arguments

`$ARGUMENTS` contains space-separated step numbers to clean (e.g., `02 03 07`).
If empty, clean ALL steps that have resources.

## Steps with Cleanable Resources

Only these steps create AWS resources that need cleanup:

| Step | Directory | Resources | Config File |
|------|-----------|-----------|-------------|
| 02 | `02_runtime/` | Agent runtime, ECR repository, config files | `.bedrock_agentcore.yaml` |
| 03 | `03_memory/` | Memory instances (prefix: `cost_estimator_memory`) | None |
| 05 | `05_evaluation/` | Custom evaluator (name: `cost_estimator_tool_usage`) | None |
| 06 | `06_identity/` | OAuth2 provider, Cognito user pool/client/domain, runtime | `inbound_authorizer.json` |
| 07 | `07_gateway/` | Gateway targets, gateway, config files | `outbound_gateway.json` |
| 08 | `08_policy/` | Policy engine, policies, Cognito app clients | `policy_config.json` |
| 09 | `09_browser_use/` | Browser sessions (ephemeral, auto-expire) | None |

## Dependency Order (CRITICAL)

Resources MUST be cleaned in reverse dependency order to avoid errors:
1. **09_browser_use** first (independent, ephemeral sessions)
2. **08_policy** second (depends on 07_gateway)
3. **07_gateway** (depends on 06_identity)
4. **06_identity** (depends on 02_runtime)
5. **05_evaluation** (independent)
6. **03_memory** (independent)
7. **02_runtime** last (other steps depend on it)

## Execution

For each step to clean, run:
```
cd <project_root>/<step_directory> && uv run python clean_resources.py
```

### Before cleaning each step:
1. Check if the config file exists (indicates resources were created)
2. If no config file, skip that step with a message
3. Run `clean_resources.py` from within the step directory (scripts use relative paths)
4. Report success or failure for each step

### Error handling:
- If a step fails, log the error and continue with remaining steps
- Report a summary at the end showing which steps succeeded/failed
- Common errors: ResourceNotFoundException (already deleted), config file missing (never created)

## Implementation

1. Parse `$ARGUMENTS` to determine which steps to clean. If empty, use all: `09 08 07 06 05 03 02`
2. Sort the requested steps in correct cleanup order: 09, 08, 07, 06, 05, 03, 02
3. Create a task list tracking each step
4. For each step (in order):
   a. Check if the step directory and config file exist
   b. If resources exist, run `clean_resources.py` from that directory
   c. Mark task as completed
5. Print a final summary
