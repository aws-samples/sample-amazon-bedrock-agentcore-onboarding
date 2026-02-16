# AgentCore Workshop 2nd Dry Run Results

Date: 2026-02-16

## Lab 1: Code Interpreter
- **Result**: PASS
- Step 1 (basic test): PASS - Cost estimation returned accurate results
- Step 2 (custom architecture): PASS - "Two EC2 m5.large instances with RDS MySQL" worked. Note: RDS pricing filter error `No results found for given filters [[PricingFilter(field='engineCode'...)]]` occurred but agent self-recovered by adjusting query parameters
- Step 3 (streaming): PASS - 162 chunks, 1829 characters received
- **Issue**: Deprecation warning `**kwargs parameter is deprecating, use invocation_state instead` shown during streaming test
- **Issue**: RDS pricing filter for `engineCode=MySQL` returns no results on first attempt; agent retries with different attributes

## Lab 2: AgentCore Runtime
- **Result**: PASS
- Step 1 (prepare_agent.py): PASS - IAM role created, deployment directory generated
- Step 2 (configure): PASS with workaround - `agentcore configure` without `--non-interactive --deployment-type direct_code_deploy` flags prompts interactively and aborts in non-terminal environments
- Step 2 (deploy): PASS - Direct code deploy succeeded, 64.41 MB package
- Step 3 (invoke): PASS - Remote agent returned accurate cost estimate ($3.80/month for t3.nano, verified 2026-02-16)
- **Issue**: prepare_agent.py output still says `agentcore launch` but correct command is `agentcore deploy`
- **Issue**: README doesn't clearly explain the `--non-interactive` and `--deployment-type` flags needed for scripted/automated execution (already noted in 1st dry run)

## Lab 3: Memory
- **Result**: PASS (after fix)
- All 4 steps completed: estimate x2, compare, wait for extraction, propose
- Memory reuse (existing memory): instant; fresh creation: ~163 seconds
- **Fixed**: `retrieve_memories()` now returns results (5 long-term memories retrieved)
  - Root cause: `userPreferenceMemoryStrategy` extracts preferences asynchronously; previous code called `propose()` before extraction completed
  - Fix: Added `wait_for_long_term_memory()` with `time.sleep(60)` per AWS docs before `retrieve_memories()` — follows official pattern from https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html
  - Kept `AWSCostEstimatorAgent` (Code Interpreter + MCP pricing) for real end-to-end demo; simplified architecture descriptions to "1 EC2 t3.nano" and "1 EC2 t3.micro with 20GB gp3 EBS" for faster execution
- Demo now runs in 4 clear steps: estimate → compare (short-term) → wait 60s for extraction → propose (long-term)

## Lab 4: Observability
- **Result**: PASS
- All 3 invocations succeeded in the same session
- Invocation 1: ~45 seconds, Invocations 2 & 3: ~57 seconds and ~18 seconds respectively
- No issues encountered

## Lab 5: Evaluation
- **Result**: PARTIAL PASS
- Local evaluation: PASS - Both test cases scored 1.00 (OutputEvaluator + ToolCallEvaluator)
- On-demand evaluation: FAIL - `BEDROCK_MODEL_ACCESS_DENIED` for model `us.anthropic.claude-3-5-sonnet-20241022-v2:0` when creating custom evaluator
- **Issue**: On-demand evaluation requires Bedrock model access for `us.anthropic.claude-3-5-sonnet-20241022-v2:0` (cross-region inference profile). This model must be enabled in the Bedrock console. README should mention this prerequisite clearly.
- Online evaluation: NOT TESTED (depends on on-demand evaluator)

## Lab 6: Identity
- **Result**: PARTIAL PASSfff
- Step 1 (setup_inbound_authorizer.py): PASS - Cognito user pool, OAuth provider, and secure runtime created successfully
- Step 2 (test_identity_agent.py): Token acquisition PASS, but Runtime invocation returned error - agent fell back to manual estimation
- **Issue**: The `cost_estimator_tool` call through the identity-protected runtime silently failed. The agent provided a manual estimate instead. The error was not clearly logged. The runtime may need time to fully initialize, or there may be an issue with the runtime invocation returning errors that are swallowed by the tool.

## Lab 7: Gateway
- **Result**: PASS
- Step 1 (deploy.sh): PASS - Lambda deployed via SAM
- Step 2 (setup_outbound_gateway.py): PASS - Gateway created, target added
- Step 3 (test_gateway.py): PASS - Cost estimation worked, Gateway `markdown_to_email` tool invoked successfully
- Email sending failed as expected (SES sandbox mode with unverified address)
- **Known issue**: `AccessDeniedException` for observability delivery destination (doesn't affect functionality, already noted in 1st dry run)

## Lab 8: Policy
- **Result**: PASS
- Step 1 (setup_policy.py): PASS - Cognito clients (Manager/Developer), Policy Engine, Cedar policy, Gateway attachment all created
- Step 2 (developer test): PASS - `markdown_to_email` correctly hidden, only `cost_estimator_tool` visible
- Step 3 (manager test): PASS - Both tools visible, policy correctly enforced
- **Minor issue**: NL2Cedar demo failed with `ConflictException: Generation with the same name already exists` (from previous run, non-critical)
- **Note**: README Step 1 command says `uv run python 08_policy/setup_policy.py` (from parent dir) but the script uses relative paths (`../06_identity/...`) that require running from `08_policy/` directory

## Lab 9: Browser Use
- **Result**: PASS
- Cost estimation + browser session + Playwright connection + form fill + submit all succeeded
- 4 screenshots saved (form_loaded, fields_filled, before_submit, after_submit)
- aria_snapshot() correctly discovered form fields
- Bedrock generated appropriate field-value mapping
- No issues encountered

## Summary

### Overall Results
- **All 9 labs executed** (2026-02-16)
- **Full PASS**: Lab 1, 2, 3, 4, 7, 8, 9
- **Partial PASS**: Lab 5 (on-demand evaluation model access), Lab 6 (runtime invocation error)

### Improvements from 1st Dry Run
- Lab 6 (Identity): `setup_inbound_authorizer.py` now works with `direct_code_deploy` (1st dry run had `containerUri: None:latest` bug) - FIXED
- Lab 7 (Gateway): `--force` flag and `UnboundLocalError` bugs were fixed - FIXED
- Lab 2 (Runtime): `agentcore deploy --env AWS_REGION=...` now documented - FIXED

### New Issues Found in 2nd Dry Run
1. **Lab 5**: On-demand evaluation fails with `BEDROCK_MODEL_ACCESS_DENIED` for `us.anthropic.claude-3-5-sonnet-20241022-v2:0`. Prerequisite needs to mention enabling this model in Bedrock console.
2. **Lab 6**: Runtime invocation through identity returns error silently - agent falls back to manual estimation without clear error logging.
3. **Lab 8**: README command `uv run python 08_policy/setup_policy.py` fails when run from parent dir due to relative paths. Must run from `08_policy/` directory.
4. **Lab 1**: Deprecation warning `**kwargs parameter is deprecating` during streaming test (cosmetic).
