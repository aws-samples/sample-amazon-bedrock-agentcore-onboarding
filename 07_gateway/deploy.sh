#!/bin/bash
# Deploy the AgentCore Gateway Lambda function using AWS SAM

set -e

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    echo "Activating virtual environment from parent directory..."
    source ../.venv/bin/activate
    echo "Virtual environment activated"
else
    echo "Warning: No virtual environment found. Using system Python."
fi

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

# Save Lambda ARN to gateway configuration for create_gateway.py
CONFIG_FILE="outbound_gateway.json"
echo "Saving Lambda ARN to $CONFIG_FILE..."

# Create or update the configuration file with Lambda ARN
cat > $CONFIG_FILE << EOF
{
  "lambda_arn": "$LAMBDA_ARN",
  "sender_email": "$SES_SENDER_EMAIL",
  "deployment_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "stack_name": "$STACK_NAME",
  "region": "$REGION",
  "tool_name": "markdown_to_email"
}
EOF

echo ""
echo "Deployment complete!"
echo "Lambda Function ARN: $LAMBDA_ARN"
echo "Sender Email: $SES_SENDER_EMAIL"
echo "Configuration saved to: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "1. Ensure your sender email ($SES_SENDER_EMAIL) is verified in Amazon SES"
echo "2. Run 'uv run python setup_outbound_gateway.py' to set up the Gateway (Lambda ARN will be read from config)"
echo "3. The Gateway will provide a 'markdown_to_email' tool that converts markdown to HTML and sends via email"
echo ""
echo "Tool usage:"
echo "- markdown_text: The markdown content to convert"
echo "- email_address: Recipient email address"
echo "- subject: Email subject (optional)"

# Deactivate virtual environment if it was activated
if [ ! -z "$VIRTUAL_ENV" ]; then
    echo "Deactivating virtual environment..."
    deactivate
fi
