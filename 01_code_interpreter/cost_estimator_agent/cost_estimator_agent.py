"""
AWS Cost Estimation Agent using Amazon Bedrock AgentCore Code Interpreter

This agent demonstrates how to:
1. Use AWS Pricing MCP Server to retrieve pricing data
2. Use AgentCore Code Interpreter for secure calculations
3. Provide comprehensive cost estimates for AWS architectures

Key Features:
- Secure code execution in AgentCore sandbox
- Real-time AWS pricing data
- Comprehensive logging and error handling
- Progressive complexity building
"""

import logging
import os
import shutil
import traceback
import boto3
from contextlib import contextmanager
from typing import Generator, AsyncGenerator
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.handlers.callback_handler import null_callback_handler
from botocore.config import Config
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from cost_estimator_agent.config import (
    SYSTEM_PROMPT,
    COST_ESTIMATION_PROMPT,
    DEFAULT_MODEL,
    LOG_FORMAT
)

# Configure comprehensive logging for debugging and monitoring
logging.basicConfig(
    level=logging.ERROR,  # Set to ERROR by default, can be changed to DEBUG for more details
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

# Enable Strands debug logging for detailed agent behavior
logging.getLogger("strands").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class AWSCostEstimatorAgent:
    """
    AWS Cost Estimation Agent using AgentCore Code Interpreter
    
    This agent combines:
    - MCP pricing tools (automatically available) for real-time pricing data
    - AgentCore Code Interpreter for secure calculations
    - Strands Agents framework for clean implementation
    """
    
    def __init__(self, region: str = ""):
        """
        Initialize the cost estimation agent
        
        Args:
            region: AWS region for AgentCore Code Interpreter
        """
        self.region = region
        if not self.region:
            # Follow AWS SDK resolution order: AWS_DEFAULT_REGION > AWS_REGION > boto3 session
            self.region = os.environ.get('AWS_DEFAULT_REGION') or os.environ.get('AWS_REGION') or boto3.Session().region_name
        self.code_interpreter = None
        
        logger.info(f"Initializing AWS Cost Estimator Agent in region: {region}")
        
    def _setup_code_interpreter(self) -> None:
        """Setup AgentCore Code Interpreter for secure calculations"""
        try:
            logger.info("Setting up AgentCore Code Interpreter...")
            self.code_interpreter = CodeInterpreter(self.region)
            self.code_interpreter.start()
            logger.info("✅ AgentCore Code Interpreter session started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to setup Code Interpreter: {e}")
            return  # Handle the error instead of re-raising
    
    def _get_aws_credentials(self) -> dict:
        """
        Get current AWS credentials (including session token if present)
        
        Returns:
            Dict with current AWS credentials including session token
        """
        try:
            logger.info("Getting current AWS credentials...")
            
            # Create session to get current credentials
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials is None:
                raise Exception("No AWS credentials found")
            
            # Verify credentials work by getting caller identity
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            logger.info(f"Using AWS identity: {identity.get('Arn', 'Unknown')}")
            
            # Get frozen credentials to access them
            frozen_creds = credentials.get_frozen_credentials()
            
            credential_dict = {
                "AWS_ACCESS_KEY_ID": frozen_creds.access_key,
                "AWS_SECRET_ACCESS_KEY": frozen_creds.secret_key,
                "AWS_REGION": self.region
            }
            
            # Add session token if available (EC2 instance role provides this)
            if frozen_creds.token:
                credential_dict["AWS_SESSION_TOKEN"] = frozen_creds.token
                logger.info("✅ Using AWS credentials with session token (likely from EC2 instance role)")
            else:
                logger.info("✅ Using AWS credentials without session token")
                
            return credential_dict
            
        except Exception as e:
            logger.error(f"❌ Failed to get AWS credentials: {e}")
            return {}  # Return empty dict as fallback

    def _setup_aws_pricing_client(self) -> MCPClient:
        """Setup AWS Pricing MCP Client with current AWS credentials"""
        try:
            logger.info("Setting up AWS Pricing MCP Client...")
            
            # Get current credentials (including session token if available)
            aws_credentials = self._get_aws_credentials()
            
            # Prepare environment variables for MCP client
            env_vars = {
                "FASTMCP_LOG_LEVEL": "ERROR",
                **aws_credentials  # Include all AWS credentials
            }
            
            # Find uvx binary: check PATH first, then fall back to uv package's bin dir
            # (in Runtime, /var/task/bin/ is not on PATH so shutil.which may fail)
            uvx_path = shutil.which("uvx")
            if not uvx_path:
                from uv._find_uv import find_uv_bin
                uv_bin = find_uv_bin()
                uvx_path = os.path.join(os.path.dirname(uv_bin), "uvx")

            aws_pricing_client = MCPClient(
                lambda: stdio_client(StdioServerParameters(
                    command=uvx_path,
                    args=["awslabs.aws-pricing-mcp-server@latest"],
                    env=env_vars
                ))
            )
            logger.info("✅ AWS Pricing MCP Client setup successfully with AWS credentials")
            return aws_pricing_client
        except Exception as e:
            logger.error(f"❌ Failed to setup AWS Pricing MCP Client: {e}")
            return None  # Return None as fallback
    
    
    @tool
    def execute_cost_calculation(self, calculation_code: str, description: str = "") -> str:
        """
        Execute cost calculations using AgentCore Code Interpreter
        
        Args:
            calculation_code: Python code for cost calculations
            description: Description of what the calculation does
            
        Returns:
            Calculation results as string
        """
        if not self.code_interpreter:
            return "❌ Code Interpreter not initialized"
            
        try:
            logger.info(f"🧮 Executing calculation: {description}")
            logger.debug(f"Code to execute:\n{calculation_code}")
            
            # Execute code in secure AgentCore sandbox
            response = self.code_interpreter.invoke("executeCode", {
                "language": "python",
                "code": calculation_code
            })
            
            # Extract results from response stream
            results = []
            for event in response.get("stream", []):
                if "result" in event:
                    result = event["result"]
                    if "content" in result:
                        for content_item in result["content"]:
                            if content_item.get("type") == "text":
                                results.append(content_item["text"])
            
            result_text = "\n".join(results)
            logger.info("✅ Calculation completed successfully")
            logger.debug(f"Calculation result: {result_text}")
            
            return result_text
            
        except Exception as e:
            logger.exception(f"❌ Calculation failed: {e}")

    @contextmanager
    def _estimation_agent(self) -> Generator[Agent, None, None]:
        """
        Context manager for cost estimation components
        
        Yields:
            Agent with all tools configured and resources properly managed
            
        Ensures:
            Proper cleanup of Code Interpreter and MCP client resources
        """        
        try:
            logger.info("🚀 Initializing AWS Cost Estimation Agent...")
            
            # Setup components in order
            self._setup_code_interpreter()
            aws_pricing_client = self._setup_aws_pricing_client()
            
            # Create agent with persistent MCP context
            with aws_pricing_client:
                pricing_tools = aws_pricing_client.list_tools_sync()
                logger.info(f"Found {len(pricing_tools)} AWS pricing tools")
                
                # Create agent with both execute_cost_calculation and MCP pricing tools
                all_tools = [self.execute_cost_calculation] + pricing_tools
                agent = Agent(
                    BedrockModel(
                        boto_client_config=Config(
                            read_timeout=900,
                            connect_timeout=900,
                            retries=dict(max_attempts=3, mode="adaptive"),
                        ),
                        model_id=DEFAULT_MODEL
                    ),
                    tools=all_tools,
                    system_prompt=SYSTEM_PROMPT
                )
                
                yield agent
                
        except Exception as e:
            logger.exception(f"❌ Component setup failed: {e}")
            raise
        finally:
            # Ensure cleanup happens regardless of success/failure
            self.cleanup()

    def estimate_costs(self, architecture_description: str) -> str:
        """
        Estimate costs for a given architecture description
        
        Args:
            architecture_description: Description of the system to estimate
            
        Returns:
            Cost estimation results as concatenated string
        """
        logger.info("📊 Starting cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # Use the agent to process the cost estimation request
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                result = agent(prompt)
                
                logger.info("✅ Cost estimation completed")

                if result.message and result.message.get("content"):
                    # Extract text from all ContentBlocks and concatenate
                    text_parts = []
                    for content_block in result.message["content"]:
                        if isinstance(content_block, dict) and "text" in content_block:
                            text_parts.append(content_block["text"])
                    return "".join(text_parts) if text_parts else "No text content found."
                else:
                    return "No estimation result."

        except Exception as e:
            logger.exception(f"❌ Cost estimation failed: {e}")
            error_details = traceback.format_exc()
            return f"❌ Cost estimation failed: {e}\n\nStacktrace:\n{error_details}"

    async def estimate_costs_stream(self, architecture_description: str) -> AsyncGenerator[dict, None]:
        """
        Estimate costs for a given architecture description with streaming response
        
        Implements proper delta-based streaming following Amazon Bedrock best practices.
        This addresses the common issue where Strands stream_async() may send overlapping
        content chunks instead of proper deltas.
        
        Args:
            architecture_description: Description of the system to estimate
            
        Yields:
            Streaming events with true delta content (only new text, no duplicates)
            
        Example usage:
            async for event in agent.estimate_costs_stream(description):
                if "data" in event:
                    print(event["data"], end="", flush=True)  # Direct printing, no accumulation needed
        """
        logger.info("📊 Starting streaming cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # Use the agent to process the cost estimation request with streaming
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                
                logger.info("🔄 Streaming cost estimation response...")
                
                # Implement proper delta handling to prevent duplicates
                # This follows Amazon Bedrock ContentBlockDeltaEvent pattern
                previous_output = ""
                
                agent_stream = agent.stream_async(prompt, callback_handler=null_callback_handler)
                
                async for event in agent_stream:
                    if "data" in event:
                        current_chunk = str(event["data"])
                        
                        # Handle delta calculation following Bedrock best practices
                        if current_chunk.startswith(previous_output):
                            # This is an incremental update - extract only the new part
                            delta_content = current_chunk[len(previous_output):]
                            if delta_content:  # Only yield if there's actually new content
                                previous_output = current_chunk
                                yield {"data": delta_content}
                        else:
                            # This is a completely new chunk or reset - yield as-is
                            previous_output = current_chunk
                            yield {"data": current_chunk}
                    else:
                        # Pass through non-data events (errors, metadata, etc.)
                        yield event
                
                logger.info("✅ Streaming cost estimation completed")

        except Exception as e:
            logger.exception(f"❌ Streaming cost estimation failed: {e}")
            # Yield error event in streaming format
            yield {
                "error": True,
                "data": f"❌ Streaming cost estimation failed: {e}\n\nStacktrace:\n{traceback.format_exc()}"
            }

    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")
        
        if self.code_interpreter:
            try:
                self.code_interpreter.stop()
                logger.info("✅ Code Interpreter session stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Code Interpreter: {e}")
            finally:
                self.code_interpreter = None
