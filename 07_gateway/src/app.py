"""
Simple Lambda function for AgentCore Gateway that converts markdown to HTML and sends via SES

This Lambda function takes markdown text and an email address, converts the markdown
to HTML, and sends it as an HTML email using Amazon SES.
"""

import json
import logging
import os
import boto3
import markdown
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))


def lambda_handler(event, context):
    """
    Handle markdown_to_email tool invocation from Gateway
    
    Args:
        event: Contains the markdown text and email address
        context: Lambda context with Gateway metadata. Its `client_context` should contain
        ClientContext(custom={
            'bedrockAgentCoreGatewayId': 'Y02ERAYBHB'
            'bedrockAgentCoreTargetId': 'RQHDN3J002'
            'bedrockAgentCoreMessageVersion': '1.0'
            'bedrockAgentCoreToolName': 'markdown_to_email'
            'bedrockAgentCoreSessionId': ''
        },env=None,client=None]

    Returns:
        Success or error message for the email sending operation
    """
    try:
        # Log the incoming request
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract tool name from context
        if context and context.client_context:
            logger.info(f"Context: {context.client_context}")
            tool_name = context.client_context.custom.get('bedrockAgentCoreToolName', '')
            
            # Remove any prefix added by Gateway (format: targetName___toolName)
            if "___" in tool_name:
                tool_name = tool_name.split("___")[-1]
        else:
            tool_name = event.get('tool_name', '')

        logger.info(f"Processing tool: {tool_name}")
        
        # Verify this is the markdown_to_email tool
        if tool_name != 'markdown_to_email':
            return {
                'statusCode': 400,
                'body': f"Unknown tool: {tool_name}"
            }
        
        # Get required parameters from event
        markdown_text = event.get('markdown_text', '')
        email_address = event.get('email_address', '')
        subject = event.get('subject', 'AWS Cost Estimation Result')
        
        if not markdown_text:
            return {
                'statusCode': 400,
                'body': "Missing required parameter: markdown_text"
            }
        
        if not email_address:
            return {
                'statusCode': 400,
                'body': "Missing required parameter: email_address"
            }

        # Convert markdown to HTML and send email
        result = convert_and_send_email(markdown_text, email_address, subject)

        return {
            'statusCode': 200,
            'body': result
        }
        
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }


def convert_and_send_email(markdown_text, email_address, subject):
    """
    Convert markdown to HTML and send via Amazon SES
    
    Args:
        markdown_text: Markdown content to convert
        email_address: Recipient email address
        subject: Email subject line
        
    Returns:
        Success message with message ID
    """
    try:
        # Convert markdown to HTML with table support
        logger.info("Converting markdown to HTML")
        html_content = markdown.markdown(
            markdown_text,
            extensions=['tables', 'nl2br']
        )
        
        # Get sender email from environment variable
        sender_email = os.environ.get('SES_SENDER_EMAIL')
        if not sender_email:
            raise ValueError("SES_SENDER_EMAIL environment variable not set")
        
        # Initialize SES client
        ses_client = boto3.client('ses')
        
        # Send email via SES
        logger.info(f"Sending email to: {email_address}")
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [email_address]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_content,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': markdown_text,  # Include plain text version
                        'Charset': 'UTF-8'
                    }
                }
            }
        )

        message_id = response['MessageId']
        logger.info(f"Email sent successfully. Message ID: {message_id}")

        return f"Email sent successfully to {email_address}. Message ID: {message_id}"
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'MessageRejected':
            logger.error(f"SES rejected the message: {error_message}")
            raise Exception(f"Email rejected by SES: {error_message}")
        elif error_code == 'MailFromDomainNotVerified':
            logger.error(f"Sender domain not verified: {error_message}")
            raise Exception(f"Sender email domain not verified in SES: {error_message}")
        else:
            logger.error(f"SES error ({error_code}): {error_message}")
            raise Exception(f"SES error: {error_message}")
            
    except Exception as e:
        logger.exception(f"Unexpected error sending email: {e}")
        raise Exception(f"Failed to send email: {str(e)}")
