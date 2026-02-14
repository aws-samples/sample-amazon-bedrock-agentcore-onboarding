# Amazon Bedrock AgentCore Onboarding

[English](README.md) / [日本語](README_ja.md)

**Practical, simple, and runnable examples** to onboard every developer to Amazon Bedrock AgentCore effectively. This project provides a progressive learning path through hands-on implementations of core AgentCore capabilities.

## Overview

Amazon Bedrock AgentCore is a comprehensive platform for building, deploying, and managing AI agents at scale. This onboarding project demonstrates each AgentCore capability through **real, working implementations** that you can run, modify, and learn from.

### What You'll Learn

**Foundation (01–05)** — Build a reliable agent
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

### 🚀 Foundation (01–05) — Build a reliable agent

1. **[Code Interpreter](01_code_interpreter/README.md)** - Start here for foundational agent development
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
→ Start with [01_code_interpreter](01_code_interpreter/README.md)

**Production-Ready Agent**
→ [02_runtime](02_runtime/README.md) → [03_memory](03_memory/README.md) → [04_observability](04_observability/README.md) → [05_evaluation](05_evaluation/README.md)

**Enterprise Security & Governance**
→ [06_identity](06_identity/README.md) → [07_gateway](07_gateway/README.md) → [08_policy](08_policy/README.md)

**End-to-End Automation**
→ [01_code_interpreter](01_code_interpreter/README.md) → [07_gateway](07_gateway/README.md) → [09_browser_use](09_browser_use/README.md)

## Prerequisites

### System Requirements
- **Python 3.11+** with `uv` package manager
- **AWS CLI** configured with appropriate permissions
- **AWS Account** with access to Bedrock AgentCore (Preview)
- **Amazon Bedrock** with model access to necessary models


### Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# Install dependencies
uv sync

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

To avoid ongoing charges, clean up resources after completing the hands-on exercises. **Clean up in reverse order (09→02) due to dependencies**:

```bash
# 1. Stop active browser sessions
uv run python 09_browser_use/clean_resources.py

# 2. Remove policy engine and Cognito resources
uv run python 08_policy/clean_resources.py

# 3. Clean up Gateway resources (uses SAM CLI)
cd 07_gateway
sam delete  # Deletes Lambda function and associated resources
uv run python clean_resources.py
cd ..

# 4. Clean up Identity resources
uv run python 06_identity/clean_resources.py

# 5. Remove evaluation configs
uv run python 05_evaluation/clean_resources.py

# 6. Clean up Memory resources
uv run python 03_memory/clean_resources.py

# 7. Clean up Runtime resources
uv run python 02_runtime/clean_resources.py
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
