#!/bin/bash
# Deploy the AgentCore Gateway Lambda function using AWS SAM
#
# The Lambda function is outside the AgentCore CLI's scope, so it is still
# deployed with SAM. The Gateway and its target are declared in agentcore.json
# and created by `agentcore deploy` — see README.md.

set -e

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    echo "Activating virtual environment from parent directory..."
    source ../.venv/bin/activate
    echo "Virtual environment activated"
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Ensure pip is available in the active environment.
# `uv venv` does not install pip by default, but SAM's PythonPipBuilder needs it
# to resolve the Lambda function's dependencies during `sam build`. Bootstrap it
# from the bundled CPython wheel, falling back to uv's pip interface.
echo "Ensuring pip is available for SAM build..."
python -m ensurepip --upgrade 2>/dev/null || uv pip install pip

STACK_NAME="AWS-Cost-Estimator-Tool-Markdown-To-Email"
REGION=$(aws configure get region 2>/dev/null || true)
if [ $# -lt 1 ]; then
    echo "Usage: $0 <ses-sender-email>"
    exit 1
fi
SES_SENDER_EMAIL="$1"


echo "Deploying Markdown-to-Email Lambda for Gateway..."
echo "Sender Email: $SES_SENDER_EMAIL"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"

# Verify sender email in SES
echo "Verifying sender email in Amazon SES..."
aws ses verify-email-identity --email-address "$SES_SENDER_EMAIL" --region "$REGION" || {
    echo "Warning: Failed to verify email address. You may need to verify it manually."
    echo "Check your email for a verification message from Amazon SES."
}


# Build the SAM application
echo "Building SAM application..."
sam build

# Deploy the SAM application
echo "Deploying SAM application..."
sam deploy \
    --stack-name $STACK_NAME \
    --region $REGION \
    --parameter-overrides "SenderEmail=$SES_SENDER_EMAIL" \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --resolve-s3

# Get the Lambda function ARN from stack outputs
LAMBDA_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='AgentCoreGatewayFunctionArn'].OutputValue" \
    --output text)

if [ -z "$LAMBDA_ARN" ]; then
    echo "Error: Could not retrieve Lambda function ARN from stack outputs"
    exit 1
fi

echo ""
echo "Deployment complete!"
echo "Lambda Function ARN: $LAMBDA_ARN"
echo "Sender Email: $SES_SENDER_EMAIL"
echo ""
echo "=============================================================================="
echo "Next steps — run these in the AgentCore project directory"
echo "=============================================================================="
echo ""
echo "# 1. Create the project (the Gateway does not need an agent of its own)"
echo "cd ../agents"
echo "agentcore create --name MyGatewayProject --no-agent --skip-git"
echo "cd MyGatewayProject"
echo ""
echo "# 2. Gateway with JWT inbound auth (reuse the Cognito from 06_identity)"
echo "agentcore add gateway \\"
echo "    --name AWSCostEstimatorGateway \\"
echo "    --protocol-type MCP \\"
echo "    --authorizer-type CUSTOM_JWT \\"
echo "    --discovery-url <discovery-url> \\"
echo "    --allowed-clients <client-id>"
echo ""
echo "# 3. Attach the Lambda as an MCP tool target"
echo "agentcore add gateway-target \\"
echo "    --name AWSCostEstimatorGatewayTarget \\"
echo "    --gateway AWSCostEstimatorGateway \\"
echo "    --type lambda-function-arn \\"
echo "    --lambda-arn $LAMBDA_ARN \\"
echo "    --tool-schema-file ../../07_gateway/tool_schema.json"
echo ""
echo "# 4. Create everything in AWS"
echo "agentcore deploy"
echo ""
echo "# 5. Verify the tool is exposed, then send an estimate"
echo "cd ../../07_gateway"
echo "uv run python test_gateway.py --list-tools"
echo "uv run python test_gateway.py --address $SES_SENDER_EMAIL"
echo ""
echo "=============================================================================="

# Deactivate virtual environment if it was activated
if [ ! -z "$VIRTUAL_ENV" ]; then
    echo "Deactivating virtual environment..."
    deactivate
fi
