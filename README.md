# Amazon Bedrock AgentCore Onboarding

[English](README.md) / [日本語](README_ja.md)

**Practical, simple, and runnable examples** to onboard every developer to Amazon Bedrock AgentCore effectively. This project provides a progressive learning path through hands-on implementations of core AgentCore capabilities.

## Overview

Amazon Bedrock AgentCore is a comprehensive platform for building, deploying, and managing AI agents at scale. This onboarding project demonstrates each AgentCore capability through **real, working implementations** that you can run, modify, and learn from.

### What You'll Learn

- **Code Interpreter**: Secure sandboxed execution for dynamic calculations and data processing
- **Runtime**: Scalable agent deployment and management in AWS cloud infrastructure  
- **Gateway**: API gateway integration with authentication and MCP protocol support
- **Identity**: OAuth 2.0 authentication and secure token management for agent operations
- **Observability**: Comprehensive monitoring, tracing, and debugging with CloudWatch integration
- **Memory**: Short-term and long-term memory capabilities for context-aware agent interactions

### Learning Philosophy

Following our **Amazon Bedrock AgentCore Implementation Principle**, every example in this project is:

- ✅ **Runnable Code First** - Complete, executable examples tested against live AWS services
- ✅ **Practical Implementation** - Real-world use cases with comprehensive logging and error handling
- ✅ **Simple and Sophisticated** - Clear, descriptive code that minimizes learning cost while maintaining functionality
- ✅ **Progressive Learning** - Numbered sequences that build complexity gradually from basic to advanced concepts

## Directory Structure

```
sample-amazon-bedrock-agentcore-onboarding/
├── 01_code_interpreter/          # Secure sandboxed execution
│   ├── README.md                 # 📖 Code Interpreter hands-on guide
│   ├── cost_estimator_agent/     # AWS cost estimation agent implementation
│   └── test_code_interpreter.py  # Complete test suite and examples
│
├── 02_runtime/                   # Agent deployment and management
│   ├── README.md                 # 📖 Runtime deployment hands-on guide
│   ├── prepare_agent.py          # Agent preparation automation tool
│   └── deployment/               # Packaged agent for deployment
│
├── 03_identity/                  # OAuth 2.0 authentication
│   ├── README.md                 # 📖 Identity integration hands-on guide
│   ├── setup_inbound_authorizer.py  # OAuth2 provider setup
│   └── test_identity_agent.py    # Identity-protected agent
│
├── 04_gateway/                   # API gateway with authentication
│   ├── README.md                 # 📖 Gateway integration hands-on guide
│   ├── setup_outbound_gateway.py # Gateway deployment automation
│   ├── src/app.py                # Lambda function implementation
│   ├── deploy.sh                 # Lambda deployment script
│   └── test_gateway.py           # Gateway test agent
│
├── 05_observability/             # Monitoring and debugging
│   ├── README.md                 # 📖 Observability setup hands-on guide
│   └── test_observability.py     # Invoke runtime several times for observability
│
├── 06_memory/                    # Context-aware interactions
│   ├── README.md                 # 📖 Memory integration hands-on guide
│   └── test_memory.py            # Memory-enhanced agent implementation
│
├── a1_custom/                    # 📚 Appendix: Build your own custom agent
│   ├── README.md                 # 📖 Custom agent development guide
│   ├── weather_agent/            # Example: Weather agent implementation
│   ├── prepare_agent.py          # Deployment preparation
│   └── test_agentcore_endpoint.py # End-to-end testing
│
├── pyproject.toml                # Project dependencies and configuration
├── uv.lock                       # Dependency lock file
└── README.md                     # This overview document
```

## Hands-On Learning Path

### 🚀 Quick Start (Recommended Order)

1. **[Code Interpreter](01_code_interpreter/README.md)** - Start here for foundational agent development
   - Build an AWS cost estimator with secure Python execution
   - Learn AgentCore basics with immediate, practical results
   - **Time**: ~10 minutes | **Difficulty**: Beginner

2. **[Runtime](02_runtime/README.md)** - Deploy your agent to AWS cloud infrastructure
   - Package and deploy the cost estimator to AgentCore Runtime
   - Understand scalable agent deployment patterns
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

3. **[Identity](03_identity/README.md)** - Add OAuth 2.0 authentication for secure operations
   - Set up Cognito OAuth provider and secure runtime
   - Implement transparent authentication with `@requires_access_token`
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

4. **[Gateway](04_gateway/README.md)** - Expose agents through MCP-compatible APIs
   - Create outbound gateway with Lambda integration
   - Combine local tools with remote gateway functionality
   - **Time**: ~15 minutes | **Difficulty**: Intermediate

5. **[Observability](05_observability/README.md)** - Monitor and debug production agents
   - Enable CloudWatch integration for comprehensive monitoring
   - Check tracing, metrics, and debugging capabilities
   - **Time**: ~15 minutes | **Difficulty**: Beginner

6. **[Memory](06_memory/README.md)** - Build context-aware, learning agents
   - Implement short-term and long-term memory capabilities
   - Create personalized, adaptive agent experiences
   - **Time**: ~15 minutes | **Difficulty**: Advanced

### 📚 Appendix

**[A1. Custom Agent](a1_custom/README.md)** - Build your own custom agent
   - Learn to create agents tailored to your specific use case
   - Example implementation provided (weather agent)
   - **Time**: ~20 minutes | **Difficulty**: Intermediate

### 🎯 Focused Learning (By Use Case)

**Building Your First Agent**
→ Start with [01_code_interpreter](01_code_interpreter/README.md)

**Production Deployment**
→ Follow [02_runtime](02_runtime/README.md) → [03_identity](03_identity/README.md) → [04_gateway](04_gateway/README.md) → [05_observability](05_observability/README.md)

**Enterprise Security**
→ Focus on [03_identity](03_identity/README.md) → [04_gateway](04_gateway/README.md)

**Advanced AI Capabilities**
[01_code_interpreter](01_code_interpreter/README.md) → Explore [06_memory](06_memory/README.md)

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

To avoid ongoing charges, clean up resources after completing the hands-on exercises. **Clean up in reverse order (06→01) due to dependencies**:

```bash
# 1. Clean up Memory resources first
cd 06_memory
uv run python clean_resources.py

# 2. Clean up Gateway resources (uses SAM CLI)
cd 04_gateway
sam delete  # Deletes Lambda function and associated resources
uv run python clean_resources.py  # Additional cleanup if needed

# 3. Clean up Identity resources
cd 03_identity
uv run python clean_resources.py

# 4. Clean up Runtime resources
cd 02_runtime
uv run python clean_resources.py

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
