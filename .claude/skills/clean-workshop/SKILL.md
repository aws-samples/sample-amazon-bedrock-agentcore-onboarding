---
name: clean-workshop
description: Clean up AWS resources created by the AgentCore workshop. Use when someone wants to tear down, clean up, or remove workshop resources.
allowed-tools: Bash, Read, Glob, Grep, Task, TaskCreate, TaskUpdate, TaskList
---

# Clean Workshop Resources

Clean up AWS resources created by the AgentCore onboarding workshop.

Each lab directory has a `clean_resources.py` that handles everything for that lab. It runs
`agentcore remove all` followed by `agentcore deploy` for CLI-managed resources (the removal is
only applied to AWS by the deploy), deletes resources outside the CLI's scope — Cognito, the
Lambda stack, browser sessions — with boto3, and verifies the result with `list-*` API calls.

**Only labs that own resources outside the CLI's scope ship a script**: 06 (Cognito),
07 (Lambda stack), 08 (Cognito demo scopes), and 09 (browser sessions). Everything in 02, 03,
and 05 is fully CLI-managed, so those are cleaned with plain `agentcore` commands.

**Prefer the scripts where they exist** — they encode the removal ordering and the cross-lab
dependency guards.

## Usage

- `/clean-workshop` — Clean all workshop resources
- `/clean-workshop 02` — Clean only step 02 (runtime)
- `/clean-workshop 02 03` — Clean steps 02 and 03
- `/clean-workshop 07 08` — Clean steps 07 and 08

## Arguments

`$ARGUMENTS` contains space-separated step numbers to clean (e.g., `02 03 07`).
If empty, clean ALL steps that have resources.

## AgentCore Projects

Resources are grouped by project, not by step. Several steps share a project.

| Project | Created by | Contains |
|---------|-----------|----------|
| `agents/MyCostEstimatorAgent` | 02 | Runtime; memory added by 03; evaluator and online eval config added by 05 |
| `agents/MyCostEstimatorAgent` | 06 | Two JWT-protected Runtimes (agent + MCP server) + credential provider, added alongside Lab 2's agent. Remove by name, never `remove all` |
| `agents/MyGatewayProject` | 07 | Gateway + target + credential; policy engine added by 08 |

## Cleanup Commands

Run in this order. Steps whose resources are used by a later lab require `--force`.

| Order | Command | What it removes |
|-------|---------|-----------------|
| 1 | `cd 09_browser_use && uv run python clean_resources.py` | Browser sessions (ephemeral) |
| 2 | `cd 08_policy && uv run python clean_resources.py` | Cedar policy, policy engine, demo Cognito scopes |
| 3 | `cd 07_gateway && uv run python clean_resources.py --force` | Gateway, target, credential, Lambda stack |
| 4 | `cd 06_identity && uv run python clean_resources.py --force` | JWT Runtime, credential provider, Cognito |
| 5 | See below (CLI only) | Evaluator, online eval config |
| 6 | See below (CLI only) | Runtime + Memory |
| 7 | See below (CLI only) | Runtime |

Steps 5–7 are fully CLI-managed:

```bash
# 5. Evaluation — keeps the runtime
cd agents/MyCostEstimatorAgent
agentcore remove online-eval --name cost_estimator_online_eval -y
agentcore remove evaluator --name cost_estimator_tool_usage -y
agentcore deploy

# 6. Memory — only the memory, the runtime stays for 04/05
cd agents/MyCostEstimatorAgent
agentcore remove memory --name MyCostEstimatorAgentMemory -y && agentcore deploy

# 7. Runtime — last step only
cd agents/MyCostEstimatorAgent
agentcore remove all -y && agentcore deploy
cd .. && rm -r MyCostEstimatorAgent
```

`remove all` empties every declaration in the project. `agents/MyCostEstimatorAgent` is
shared by labs 02, 03, 05, and 06, so this belongs in the **final** step only. Mid-sequence,
remove resources by name: `agentcore remove <kind> --name <name>`.

Useful flags:

- `07_gateway --keep-lambda` — keep the SAM-deployed Lambda stack
- `06_identity` without `--force` — removes the AgentCore resources but keeps Cognito

## Dependency Order (CRITICAL)

The scripts guard the cross-lab dependencies, but the order still matters:

1. **09_browser_use** first (independent, ephemeral sessions)
2. **08_policy** second (its policy engine is attached to 07's gateway)
3. **07_gateway** (needs `--force`: 08 depends on this gateway)
4. **06_identity** (needs `--force` to delete Cognito, which 07 and 08 also use)
5. **05_evaluation** (CLI only — its resources live in 02's project)
6. **03_memory** (CLI only — removes just the memory from 02's project)
7. **02_runtime** last (CLI only — 04 and 05 depend on this runtime)

Within a project, referencing resources must be removed first:

- `online-eval` before `evaluator` (`Evaluator ... is referenced by online eval config(s)`)
- `policy` before `policy-engine`

The scripts for 06–09 already handle this ordering internally. For 05 the order has to be
followed by hand, as shown above.

Steps 01 and 04 create no cloud resources of their own — 01 runs locally and 04 observes 02's
runtime — so there is nothing to clean.

## Verification

Each script verifies its own scope and prints `✅` or `⚠️`. To check everything at once:

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE REVIEW_IN_PROGRESS \
  --query 'StackSummaries[?starts_with(StackName,`AgentCore-My`)].[StackName,StackStatus]'
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[?starts_with(agentRuntimeName,`My`)].agentRuntimeName'
aws bedrock-agentcore-control list-memories --query 'memories[?starts_with(id,`My`)].id'
aws bedrock-agentcore-control list-evaluators \
  --query 'evaluators[?contains(evaluatorName,`cost_estimator`)].evaluatorName'
aws bedrock-agentcore-control list-gateways \
  --query 'items[?starts_with(name,`mygatewayproject`)].name'
aws cognito-idp list-user-pools --max-results 20 \
  --query 'UserPools[?starts_with(Name,`agentcore-cost-estimator`)].Name'
```

All should return `[]`. `Builtin.*` evaluators are provided by AgentCore and need no cleanup.

## Error handling

- If a step fails, log the error and continue with remaining steps
- A script exits non-zero when its verification still finds resources — re-run it
- Labs 02, 03, and 05 have no script; verify them with the `list-*` queries below
- `agentcore remove all` succeeding but `agentcore deploy` failing means the AWS resources are
  still there — retry the deploy
- A stack stuck in `REVIEW_IN_PROGRESS` or `ROLLBACK_COMPLETE` blocks `agentcore deploy`; delete
  it directly: `aws cloudformation delete-stack --stack-name AgentCore-<project>-default`
- Common non-errors: ResourceNotFoundException (already deleted), missing project directory
  (never created). The scripts report these as "nothing to clean" and exit 0
- A full project teardown takes 1–2 minutes because CloudFormation deletes the stack

## Implementation

1. Parse `$ARGUMENTS` to determine which steps to clean. If empty, use all: `09 08 07 06 05 03 02`
2. Sort the requested steps in cleanup order: 09, 08, 07, 06, 05, 03, 02
3. Create a task list tracking each step
4. For each step (in order):
   a. For 09, 08, 07, 06: run `uv run python clean_resources.py` from that lab directory,
      adding `--force` for 07 and 06
   b. For 05, 03, 02: run the `agentcore` commands shown above from the project directory
   c. The scripts skip themselves when nothing exists — no need to pre-check
   d. Mark task as completed, noting whether verification printed `✅`
5. Run the verification commands above
6. Print a final summary
