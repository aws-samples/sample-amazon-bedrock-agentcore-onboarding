# Amazon Bedrock AgentCore Implementation Principle

## Purpose

This guide establishes the development principles for the **sample-amazon-bedrock-agentcore-onboarding** project. Our mission is to provide **practical, simple, and runnable codes** to onboard every developer to Amazon Bedrock AgentCore effectively.

## Goal

Our goal is publishing `agentcore_blog_ja.md` with **PERFECT** practical, simple and runnable examples.

## Core Implementation Principles

### 1. Runnable Code First
- **Always refer to the latest AWS documentation** before implementation to guarantee code reliability
- Verify all code examples work with current AWS SDK versions and service APIs
- Test implementations against live AWS services when possible
- Include complete, executable examples rather than code fragments
- Provide clear setup instructions and prerequisites
- **Use meaningful, descriptive filenames** that clearly indicate purpose and functionality

### 2. Practical Implementation
- **Add comprehensive comments and logging** to allow developers to monitor and debug behavior
- Include error handling patterns and troubleshooting guidance
- Provide real-world use cases and scenarios
- Explain the "why" behind implementation decisions
- Include performance considerations and best practices
- **Create progressive learning paths** with numbered sequences that build complexity gradually

### 3. Simple and Sophisticated
- **Keep code simple and sophisticated** to minimize learning cost
- Use clear, descriptive variable and function names
- Follow consistent coding patterns throughout the project
- Avoid unnecessary complexity while maintaining functionality
- Provide step-by-step explanations for complex concepts
- **Prefer flat, simple directory structures** over deep hierarchies for better navigation and understanding

## Developer Guidelines

### Project Structure Principles
- **Start simple, evolve as needed** - Begin with minimal structure and add complexity only when necessary
- **Use numbered sequences for learning paths** - Organize content as 01-, 02-, 03- to create clear progression
- **Meaningful names over conventions** - Choose descriptive names that explain purpose rather than generic terms
- **Documentation-first approach** - Create README.md files to clarify purpose before implementing code
- **One concept per directory** - Each section should focus on a single AgentCore capability or concept

### Code Structure
- Start with basic examples and progressively build complexity
- Use modular design to allow developers to understand components independently
- Include both synchronous and asynchronous implementation patterns where applicable
- Provide configuration templates and environment setup guides

### Documentation Standards
- Every code example must include:
  - Purpose and use case explanation
  - Required AWS permissions and setup
  - Step-by-step execution instructions
  - Expected outputs and results
  - Common troubleshooting scenarios

### Logging and Monitoring
- Implement structured logging for all operations
- Include debug-level logging for development environments
- Provide examples of CloudWatch integration
- Show how to monitor AgentCore performance and behavior

### Error Handling
- Demonstrate proper exception handling patterns
- Include retry logic with exponential backoff
- Provide clear error messages and resolution steps
- Show how to handle common AWS service errors

## Key Implementation Learnings

### Structure Design Insights
- **Simplicity accelerates learning** - Flat directory structures reduce cognitive load and improve navigation
- **Context drives decisions** - Understanding the learner's journey should inform all structural choices
- **Avoid premature optimization** - Don't create complex structures until they demonstrate clear value

### Development Process Insights
- **Documentation-first reduces rework** - Starting with README.md clarifies purpose and prevents scope creep
- **Iterative refinement works** - Start minimal, gather feedback, then evolve based on actual needs
- **User perspective matters** - Always consider how developers will discover, navigate, and use the materials

### Code Quality and Authenticity Insights
- **No dummy data ever** - Remove all placeholder/sample data and use real API connections and service integrations
- **Practical over perfect** - Show real implementation challenges rather than idealized examples with fake data
- **Authentic complexity** - Don't hide the real complexity of integrations behind dummy responses
- **Separate configuration from logic** - Extract prompts, constants, and configuration to pass linting tools like ruff
- **Follow language conventions** - Use underscores instead of hyphens for Python package compatibility
- **Meaningful naming** - Use descriptive filenames like `cost_estimator_agent.py` instead of generic names

### Resource Management and Integration Insights
- **Always implement cleanup** - Follow service-specific cleanup patterns (e.g., AgentCore Code Interpreter requires explicit session stopping)
- **Use try/finally blocks** - Ensure resources are cleaned up even when errors occur to prevent resource leaks
- **Document resource lifecycle** - Explain why cleanup is necessary for each service and the consequences of not doing it
- **Multi-service coordination complexity** - Real agents often combine multiple services (MCP + AgentCore + Strands) with cascading dependencies
- **Service-specific patterns** - Each AWS service has its own best practices, error patterns, and resource management requirements

### Execution Environment Insights
- **Match actual project setup** - Use `uv run` commands and directory structures that match the real development environment
- **Version-specific guidance** - Reference specific SDK versions and service capabilities rather than generic instructions
- **Real prerequisites** - List actual AWS permissions, service access requirements, and setup steps needed for success

### Testing and Validation Insights
- **Simple tests over complex test suites** - Create focused, single-purpose tests that demonstrate core functionality clearly
- **Step-by-step test validation** - Tests should show initialization, core functionality, and cleanup in clear steps
- **Testimonial-style testing** - Tests should serve as working examples that demonstrate value to users
- **Test documentation in README** - Add test instructions directly to existing README.md rather than creating separate test files

### Real-World Debugging Insights
- **Debug actual API responses** - Use logging to understand real data structures before assuming field names from documentation
- **Verify basics first** - Check URL formats, parameter names, and service names against official documentation before implementing complex solutions
- **Implement incremental state saves** - Save configuration after each successful step to enable partial failure recovery and easier debugging
- **Cross-reference multiple sources** - When convenience methods fail, examine toolkit source code and API documentation together

## Implementation Checklist

Before submitting any code example, ensure:

- [ ] Code runs successfully with latest AWS SDK
- [ ] All dependencies are clearly documented
- [ ] Comprehensive comments explain each major step
- [ ] Logging is implemented for debugging
- [ ] Error handling covers common scenarios
- [ ] README or inline documentation explains setup
- [ ] Code follows consistent formatting standards
- [ ] Examples are as simple as possible while being complete
- [ ] **No dummy or placeholder data** - all integrations use real services
- [ ] **Proper resource cleanup** - includes try/finally blocks for resource management
- [ ] **Meaningful filenames** - descriptive names that indicate purpose and functionality
- [ ] **Separated configuration** - prompts and constants extracted to pass linting tools
- [ ] **Correct execution commands** - uses `uv run` with proper directory structure
- [ ] **Service-specific patterns** - follows best practices for each AWS service used
- [ ] **Debug actual object structures** - Log API responses to verify field names match expectations
- [ ] **Implement incremental state management** - Save configuration after each successful step for partial failure recovery

## Commitment

**All developers are expected to follow these principles** to maintain consistency and quality across the Amazon Bedrock AgentCore onboarding experience. By adhering to these guidelines, we ensure that every developer can successfully implement and understand Amazon Bedrock AgentCore capabilities.

Remember: Our goal is to make Amazon Bedrock AgentCore accessible to developers of all skill levels through practical, runnable, and well-documented examples.

---

**We need to update this principle from our learning.**
