# Amazon Bedrock AgentCore Onboarding

[English](README.md) / [日本語](README_ja.md)

**Practical, simple, and runnable examples** to onboard every developer to Amazon Bedrock AgentCore effectively. This project provides a progressive learning path through hands-on implementations of core AgentCore capabilities.

## Overview

Amazon Bedrock AgentCore is a comprehensive platform for building, deploying, and managing AI agents at scale. This onboarding project demonstrates each AgentCore capability through **real, working implementations** that you can run, modify, and learn from.

### What You'll Learn

**Foundation** — Build a reliable agent
- **Code Interpreter**: Secure sandboxed execution for dynamic calculations and data processing
- **Runtime**: Scalable agent deployment and management in AWS cloud infrastructure
- **Memory**: Short-term and long-term memory capabilities for context-aware agent interactions
- **Observability**: Comprehensive monitoring, tracing, and debugging with CloudWatch integration
- **Evaluation**: Quality assurance with built-in and custom evaluators

**Extension (06–09)** — Connect to external systems to enhance capability
- **Identity**: OAuth 2.0 authentication and secure token management for agent operations
- **Gateway**: API gateway integration with authentication and MCP protocol support
- **Policy**: Fine-grained access control for agent-to-tool interactions with Cedar
- **Browser Use**: Web automation for form-only systems with managed browser sessions

**Appendix** — Build your own
- **Custom Agent**: Apply learned patterns to create agents tailored to your specific use case

### Learning Philosophy

Following our **Amazon Bedrock AgentCore Implementation Principle**, every example in this project is:

- ✅ **Runnable Code First** - Complete, executable examples tested against live AWS services
- ✅ **Practical Implementation** - Real-world use cases with comprehensive logging and error handling
- ✅ **Simple and Sophisticated** - Clear, descriptive code that minimizes learning cost while maintaining functionality
- ✅ **Progressive Learning** - Numbered sequences that build complexity gradually from basic to advanced concepts

## Hands-On Learning Path

### 🚀 Foundation — Build a reliable agent

1. **[Code Interpreter](agents/CostEstimatorAgent/app/CostEstimatorAgent/README.md)** - Start here for foundational agent development
   - Build an AWS cost estimator with secure Python execution
   - Learn AgentCore basics with immediate, practical results
   - **Time**: ~10 minutes | **Difficulty**: Beginner

2. **[Runtime](02_runtime/README.md)** - Deploy your agent to AWS cloud infrastructure
   - Package and deploy the cost estimator to AgentCore Runtime
   - Understand scalable agent deployment patterns
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

3. **[Memory](03_memory/README.md)** - Build context-aware, learning agents
   - Implement short-term and long-term memory capabilities
   - Create personalized, adaptive agent experiences
   - **Time**: ~15 minutes | **Difficulty**: Advanced

4. **[Observability](04_observability/README.md)** - Monitor and debug production agents
   - Enable CloudWatch integration for comprehensive monitoring
   - Check tracing, metrics, and debugging capabilities
   - **Time**: ~15 minutes | **Difficulty**: Beginner

5. **[Evaluation](05_evaluation/README.md)** - Ensure agent quality with an evaluation-first mindset
   - Run local, on-demand, and online evaluation against the cost estimator
   - Build a custom `ToolCallEvaluator` and deploy it to AgentCore
   - **Time**: ~20 minutes | **Difficulty**: Intermediate

### 🔗 Extension (06–09) — Connect to external systems to enhance capability

6. **[Identity](06_identity/README.md)** - Add OAuth 2.0 authentication for secure operations
   - Set up Cognito OAuth provider and secure runtime
   - Implement transparent authentication with `@requires_access_token`
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

7. **[Gateway](07_gateway/README.md)** - Expose agents through MCP-compatible APIs
   - Create outbound gateway with Lambda integration
   - Combine local tools with remote gateway functionality
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

8. **[Policy](08_policy/README.md)** - Control agent-to-tool interactions with Cedar
   - Define role-based access policies (Manager vs Developer) for Gateway tools
   - Deploy a Cedar policy engine in ENFORCE mode
   - **Time**: ~15 minutes | **Difficulty**: Advanced

9. **[Browser Use](09_browser_use/README.md)** - Automate web-based workflows
   - Fill and submit web forms using AgentCore Browser managed sessions
   - Combine cost estimation with Playwright-based form automation
   - **Time**: ~10 minutes | **Difficulty**: Intermediate

### 📚 Appendix — Build your own

**[A1. Custom Agent](a1_custom/README.md)** - Apply what you've learned to build your own agent
   - Create agents tailored to your specific use case
   - Example implementation provided (weather agent)
   - **Time**: ~20 minutes | **Difficulty**: Intermediate

### 🎯 Focused Learning (By Use Case)

**Building Your First Agent**
→ Start with [agents/CostEstimatorAgent](agents/CostEstimatorAgent/app/CostEstimatorAgent/README.md)

**Production-Ready Agent**
→ [02_runtime](02_runtime/README.md) → [03_memory](03_memory/README.md) → [04_observability](04_observability/README.md) → [05_evaluation](05_evaluation/README.md)

**Enterprise Security & Governance**
→ [06_identity](06_identity/README.md) → [07_gateway](07_gateway/README.md) → [08_policy](08_policy/README.md)

**End-to-End Automation**
→ [agents/CostEstimatorAgent](agents/CostEstimatorAgent/app/CostEstimatorAgent/README.md) → [07_gateway](07_gateway/README.md) → [09_browser_use](09_browser_use/README.md)

## Prerequisites

### System Requirements
- **Python 3.12+** with `uv` package manager
- **AWS CLI** configured with appropriate permissions
- **AWS Account** with access to Bedrock AgentCore (Preview)
- **Amazon Bedrock** with model access to necessary models
- **Node.js 20+** and the **AgentCore CLI** (`npm install -g @aws/agentcore`)
- **AWS CDK** — used internally by `agentcore deploy`. Run `cdk bootstrap` once per target region
- **AWS SAM CLI** — required to deploy the Lambda in 07_gateway


### Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# Install dependencies
uv sync

# Install the AgentCore CLI
npm install -g @aws/agentcore
agentcore --version

# Bootstrap the CDK (once per region)
cdk bootstrap

# Verify AWS configuration
aws sts get-caller-identity
```

You can use one click environmental setup on AWS (it costs for AWS service usage).

[![](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://us-west-2.console.aws.amazon.com/cloudformation/home#/stacks/create/review?stackName=AIAgentDevelopmentCodeServerDeploymentStack&templateURL=https://aws-ml-jp.s3.ap-northeast-1.amazonaws.com/asset-deployments/AIAgentDevelopmentCodeServerDeploymentStack.yaml) 

## Key Features

### 🔧 **Real Implementation Focus**
- No dummy data or function
- All examples connect to actual use cases
- Authentic complexity and error handling patterns

### 📚 **Progressive Learning Design**
- Each directory builds on previous concepts
- Clear prerequisites and dependencies
- Step-by-step execution instructions

### 🔍 **Debugging-Friendly**
- Extensive logging for monitoring behavior
- Clear error messages and troubleshooting guidance
- Incremental state management for partial failure recovery

## Resource Cleanup

### 🧹 **Important: Clean Up AWS Resources**

To avoid ongoing charges, clean up resources after completing the hands-on exercises.

Remove CLI-managed resources with `agentcore remove all`, then apply the removal to AWS with
`agentcore deploy`. **`remove` alone leaves the AWS resources in place.** Exercises that also
own resources outside the CLI's scope (Cognito, Lambda, browser sessions) — 06, 07, 08, 09 —
ship a `clean_resources.py` that handles both.
**Clean up in reverse order (09→02) due to dependencies**:

```bash
# 1. Browser Use — stop active browser sessions
cd 09_browser_use && uv run python clean_resources.py && cd ..

# 2. Policy — Cedar policy, policy engine, demo scopes
cd 08_policy && uv run python clean_resources.py && cd ..

# 3. Gateway — gateway / target / credential and the Lambda stack
cd 07_gateway && uv run python clean_resources.py --force && cd ..

# 4. Identity — the two runtimes and credential provider 06 added, plus Cognito
#    (Lab 2's agent survives)
cd 06_identity && uv run python clean_resources.py --force && cd ..

# 5. Evaluation — evaluator and online eval config (keeps the runtime)
cd agents/MyCostEstimatorAgent
agentcore remove online-eval --name cost_estimator_online_eval -y
agentcore remove evaluator --name cost_estimator_tool_usage -y
agentcore deploy
cd ../..

# 6. Memory — remove only the memory added to Lab 2's project
cd agents/MyCostEstimatorAgent
agentcore remove memory --name MyCostEstimatorAgentMemory -y && agentcore deploy
cd ../..

# 7. Runtime — the base agent (last step only)
cd agents/MyCostEstimatorAgent
agentcore remove all -y && agentcore deploy
cd .. && rm -r MyCostEstimatorAgent && cd ..
```

`agentcore remove all` empties every declaration in the project. `agents/MyCostEstimatorAgent`
is shared by exercises 02, 03, 05, and 06, so use it **only as the final step**. Mid-sequence,
remove resources by name with `agentcore remove <kind> --name <name>`.

The scripts for 07 and 06 require `--force` because later exercises depend on their resources.
Each script verifies the deletion with `list-*` API calls and reports the outcome as
`✅` or `⚠️`.

Exercises 01 and 04 create no cloud resources of their own — 01 runs locally and 04 only
observes 02's runtime. Everything in 02, 03, and 05 is managed by the AgentCore CLI, so no
script is needed there.

Verify everything is gone:

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE REVIEW_IN_PROGRESS \
  --query 'StackSummaries[?starts_with(StackName,`AgentCore-My`)].[StackName,StackStatus]'
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[?starts_with(agentRuntimeName,`My`)].agentRuntimeName'
aws bedrock-agentcore-control list-memories --query 'memories[?starts_with(id,`My`)].id'
aws cognito-idp list-user-pools --max-results 20 \
  --query 'UserPools[?starts_with(Name,`agentcore-cost-estimator`)].Name'
```

## Getting Help

### Common Issues
- **AWS Permissions**: Ensure your credentials have the required permissions listed above
- **Service Availability**: AgentCore is in Preview - check region availability
- **Dependencies**: Use `uv sync` to ensure consistent dependency versions
- **Resource Cleanup**: Always run cleanup scripts in reverse order to avoid unexpected charges

### Support Resources

- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AWS Support](https://aws.amazon.com/support/) for account-specific issues
- [GitHub Issues](https://github.com/aws-samples/sample-amazon-bedrock-agentcore-onboarding/issues) for project-specific questions


## Contributing

We welcome contributions that align with our **Implementation Principle**:

1. **Runnable Code First** - All examples must work with current AWS SDK versions
2. **Practical Implementation** - Include comprehensive comments and real-world use cases
3. **Simple and Sophisticated** - Maintain clarity while preserving functionality
4. **Meaningful Structure** - Use descriptive names and logical organization

See our [Contribution Guideline](CONTRIBUTING.md) for detailed guidelines.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.
