"""
AWS Cost Estimator Agent with AgentCore Memory

This implementation demonstrates AgentCore Memory capabilities by enhancing
the AWS Cost Estimator with both short-term and long-term memory features.

Key Features:
1. Short-term Memory: Stores multiple cost estimations within a session for comparison
2. Long-term Memory: Learns user decision patterns and preferences over time
3. Comparison Feature: Enables side-by-side comparison of multiple estimates
4. Decision Insights: Provides personalized recommendations based on historical patterns

The AgentWithMemory class integrates memory functionality with the existing
cost estimator agent, providing a comprehensive example of memory usage patterns.
"""

import sys
import os
import logging
import traceback
import argparse
import json
import boto3
from datetime import datetime

# Configure logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import from 01_code_interpreter
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "01_code_interpreter"))

from strands import Agent, tool  # noqa: E402
from bedrock_agentcore.memory.client import MemoryClient  # noqa: E402
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent  # noqa: E402

# Prompt Templates
SYSTEM_PROMPT = """You are an AWS Cost Estimator Agent with memory capabilities.

You can help users with:
1. estimate: Calculate costs for AWS architectures
2. compare: Compare multiple cost estimates side-by-side
3. propose: Recommend optimal architecture based on user preferences and history

Always provide detailed explanations and consider the user's historical preferences
when making recommendations."""

COMPARISON_PROMPT_TEMPLATE = """Compare the following AWS cost estimates and provide insights:

User Request: {request}

Estimates:
{estimates}

Please provide:
1. A summary of each estimate
2. Key differences between the architectures
3. Cost comparison insights
4. Recommendations based on the comparison
"""

PROPOSAL_PROMPT_TEMPLATE = """Generate an AWS architecture proposal based on the following:

User Requirements: {requirements}

Historical Preferences and Patterns:
{historical_data}

Please provide:
1. Recommended architecture overview
2. Key components and services
3. Estimated costs (rough estimates)
4. Scalability considerations
5. Security best practices
6. Cost optimization recommendations

Make the proposal personalized based on any available historical preferences.
"""


class AgentWithMemory:
    """
    AWS Cost Estimator Agent enhanced with AgentCore Memory capabilities
    
    This class demonstrates the practical distinction between short-term and
    long-term memory through cost estimation and comparison features:
    
    - Short-term memory: Stores estimates within session for immediate comparison
    - Long-term memory: Learns user preferences and decision patterns over time
    """
    
    def __init__(self, actor_id: str, region: str = "", force_recreate: bool = False):
        """
        Initialize the agent with memory capabilities
        
        Args:
            actor_id: Unique identifier for the user/actor (used for memory namespace)
            region: AWS region for AgentCore services
            force_recreate: If True, delete existing memory and create new one
        """
        self.actor_id = actor_id
        self.region = region
        if not self.region:
            # Use default region from boto3 session if not specified
            self.region = boto3.Session().region_name
        self.force_recreate = force_recreate
        self.memory_id = None
        self.memory = None
        self.memory_client = None
        self.agent = None
        self.bedrock_runtime = None
        self.session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(f"Initializing AgentWithMemory for actor: {actor_id}")
        if force_recreate:
            logger.info("🔄 Force recreate mode enabled - will delete existing memory")
        
        # Initialize AgentCore Memory with user preference strategy
        try:
            logger.info("Initializing AgentCore Memory...")
            self.memory_client = MemoryClient(region_name=self.region)
            
            # Check if memory already exists
            memory_name = "cost_estimator_memory"
            existing_memories = self.memory_client.list_memories()
            existing_memory = None
            for memory in existing_memories:
                if memory.get('memoryId').startswith(memory_name):
                    existing_memory = memory
                    break

            if existing_memory:
                if not force_recreate:
                    # Reuse existing memory (default behavior)
                    self.memory_id = existing_memory.get('id')
                    self.memory = existing_memory
                    logger.info(f"🔄 Reusing existing memory: {memory_name} (ID: {self.memory_id})")
                    logger.info("✅ Memory reuse successful - skipping creation time!")
                else:            
                    # Delete existing memory if force_recreate is True
                    memory_id_to_delete = existing_memory.get('id')
                    logger.info(f"🗑️ Force deleting existing memory: {memory_name} (ID: {memory_id_to_delete})")
                    self.memory_client.delete_memory_and_wait(memory_id_to_delete, max_wait=300)
                    logger.info("✅ Existing memory deleted successfully")
                    existing_memory = None

            if existing_memory is None:
                # Create new memory
                logger.info("Creating new AgentCore Memory...")
                self.memory = self.memory_client.create_memory_and_wait(
                    name=memory_name,
                    strategies=[{
                        "userPreferenceMemoryStrategy": {
                            "name": "UserPreferenceExtractor",
                            "description": "Extracts user preferences for AWS architecture decisions",
                            "namespaces": [f"/preferences/{self.actor_id}"]
                        }
                    }],
                    event_expiry_days=7,  # Minimum allowed value
                )
                self.memory_id = self.memory.get('memoryId')
                logger.info(f"✅ AgentCore Memory created successfully with ID: {self.memory_id}")

            # Initialize Bedrock Runtime client for AI-powered features
            self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=self.region)
            logger.info("✅ Bedrock Runtime client initialized")
            
            # Create the agent with cost estimation tools and callback handler
            self.agent = Agent(
                tools=[self.estimate, self.compare, self.propose],
                system_prompt=SYSTEM_PROMPT
            )
            
        except Exception as e:
            logger.exception(f"❌ Failed to initialize AgentWithMemory: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self.agent

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - preserves memory by default for debugging"""
        # Memory is preserved by default to speed up debugging
        # Use --force to recreate memory when needed
        try:
            if self.memory_client and self.memory_id:
                logger.info("🧹 Memory preserved for reuse (use --force to recreate)")
                logger.info("✅ Context manager exit completed")
        except Exception as e:
            logger.warning(f"⚠️ Error in context manager exit: {e}")

    def list_memory_events(self, max_results: int = 10):
        """Helper method to inspect memory events for debugging"""
        try:
            if not self.memory_client or not self.memory_id:
                return "❌ Memory not available"
            
            events = self.memory_client.list_events(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                max_results=max_results
            )
            
            logger.info(f"📋 Found {len(events)} events in memory")
            for i, event in enumerate(events):
                logger.info(f"Event {i+1}: {json.dumps(event, indent=2, default=str)}")
            
            return events
        except Exception as e:
            logger.error(f"❌ Failed to list events: {e}")
            return []

    @tool
    def estimate(self, architecture_description: str) -> str:
        """
        Estimate costs for an AWS architecture
        
        Args:
            architecture_description: Description of the AWS architecture to estimate
            
        Returns:
            Cost estimation results
        """
        try:
            logger.info(f"🔍 Estimating costs for: {architecture_description}")
            
            # Use the existing cost estimator agent
            cost_estimator = AWSCostEstimatorAgent(region=self.region)
            result = cost_estimator.estimate_costs(architecture_description)
            # Store event in memory
            logger.info("Store event to short term memory")
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=self.actor_id,
                session_id=self.session_id,
                messages=[
                    (architecture_description, "USER"),
                    (result, "ASSISTANT")
                ]
            )

            # The memory hook will automatically store this interaction
            logger.info("✅ Cost estimation completed")
            return result
            
        except Exception as e:
            logger.exception(f"❌ Cost estimation failed: {e}")
            return f"❌ Cost estimation failed: {e}"

    @tool
    def compare(self, request: str = "Compare my recent estimates") -> str:
        """
        Compare multiple cost estimates from memory
        
        Args:
            request: Description of what to compare
            
        Returns:
            Detailed comparison of estimates
        """
        logger.info("📊 Retrieving estimates for comparison...")
        
        if not self.memory_client or not self.memory_id:
            return "❌ Memory not available for comparison"
        
        # Retrieve recent estimate events from memory
        events = self.memory_client.list_events(
            memory_id=self.memory_id,
            actor_id=self.actor_id,
            session_id=self.session_id,
            max_results=4
        )
        
        # Filter and parse estimate tool calls
        estimates = []
        for event in events:
            try:
                # Extract payload data
                _input = ""
                _output = ""
                for payload in event.get('payload', []):
                    if 'conversational' in payload:
                        _message = payload['conversational']
                        _role = _message.get('role', 'unknown')
                        _content = _message.get('content')["text"]

                        if _role == 'USER':
                            _input = _content
                        elif _role == 'ASSISTANT':
                            _output = _content
                    
                    if _input and _output:
                        estimates.append(
                            "\n".join([
                                "## Estimate",
                                f"**Input:**:\n{_input}",
                                f"**Output:**:\n{_output}"
                            ])
                        )
                        _input = ""
                        _output = ""

            except Exception as parse_error:
                logger.warning(f"Failed to parse event: {parse_error}")
                continue
        
        if not estimates:
            raise Exception("ℹ️ No previous estimates found for comparison. Please run some estimates first.") 
        
        # Generate comparison using Bedrock
        logger.info(f"🔍 Comparing {len(estimates)} estimates... {estimates}")
        comparison_prompt = COMPARISON_PROMPT_TEMPLATE.format(
            request=request,
            estimates="\n\n".join(estimates)
        )
        
        comparison_result = self._generate_with_bedrock(comparison_prompt)
        
        logger.info(f"✅ Comparison completed for {len(estimates)} estimates")
        return comparison_result

    @tool
    def propose(self, requirements: str) -> str:
        """
        Propose optimal architecture based on user preferences and history
        
        Args:
            requirements: User requirements for the architecture
            
        Returns:
            Personalized architecture recommendation
        """
        try:
            logger.info("💡 Generating architecture proposal based on user history...")
            
            if not self.memory_client or not self.memory_id:
                return "❌ Memory not available for personalized recommendations"
            
            # Retrieve user preferences and patterns from long-term memory
            memories = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=f"/preferences/{self.actor_id}",
                query=f"User preferences and decision patterns for: {requirements}",
                top_k=3
            )
            contents = [memory.get('content', {}).get('text', '') for memory in memories]

            # Generate proposal using Bedrock
            logger.info(f"🔍 Generating proposal with requirements: {requirements}\nHistorical data: {contents}")
            proposal_prompt = PROPOSAL_PROMPT_TEMPLATE.format(
                requirements=requirements,
                historical_data="\n".join(contents) if memories else "No historical data available"
            )
            
            proposal = self._generate_with_bedrock(proposal_prompt)
            
            logger.info("✅ Architecture proposal generated")
            return proposal
            
        except Exception as e:
            logger.exception(f"❌ Proposal generation failed: {e}")
            return f"❌ Proposal generation failed: {e}"

    def _generate_with_bedrock(self, prompt: str) -> str:
        """
        Generate content using Amazon Bedrock Converse API
        
        Args:
            prompt: The prompt to send to Bedrock
            
        Returns:
            Generated content from Bedrock
        """
        try:
            # Use Claude Sonnet 4 for fast, cost-effective generation
            model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
            
            # Prepare the message
            messages = [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ]
            
            # Invoke the model using Converse API
            response = self.bedrock_runtime.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 4000,
                    "temperature": 0.9
                }
            )
            
            # Extract the response text
            output_message = response['output']['message']
            generated_text = output_message['content'][0]['text']
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Bedrock generation failed: {e}")
            # Fallback to a simple response if Bedrock fails
            return f"⚠️ AI generation failed. Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="AWS Cost Estimator Agent with AgentCore Memory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_memory.py              # Reuse existing memory (fast debugging)
  python test_memory.py --force      # Force recreate memory (clean start)
        """
    )
    parser.add_argument(
        '--force', 
        action='store_true',
        help='Force delete and recreate memory (slower but clean start)'
    )
    
    args = parser.parse_args()
    
    print("🚀 AWS Cost Estimator Agent with AgentCore Memory")
    print("=" * 60)
    
    if args.force:
        print("🔄 Force mode: Will delete and recreate memory")
    else:
        print("⚡ Fast mode: Will reuse existing memory")
    
    try:
        # Use context manager to ensure proper cleanup
        with AgentWithMemory(actor_id="user123", force_recreate=args.force) as agent:
            print("\n📝 Running cost estimates for different architectures...")
            
            # Estimate costs for three different architectures
            architectures = [
                "Single EC2 t3.micro instance with RDS MySQL for a small blog",
                "Load balanced EC2 t3.small instances with RDS MySQL for medium traffic web app"
            ]
            
            print("\n🔍 Generating estimates...")
            for i, architecture in enumerate(architectures, 1):
                print(f"\n--- Estimate #{i} ---")
                result = agent(f"Please estimate architecture: {architecture}")
                print(result)
                result_text = result.message["content"] if result.message else "No estimation result."
                print(f"Architecture: {architecture}")
                print(f"Result: {result_text[:200]}..." if len(result_text) > 200 else result_text)

            print("\n" + "="*60)
            print("📊 Comparing all estimates...")
            comparison = agent("Could you please compare the estimates I just generated?")
            print(comparison)

            print("\n" + "="*60)
            print("💡 Getting personalized recommendation...")
            proposal = agent("Could you please propose best architecture for my preference?")
            print(proposal)            
            
    except Exception as e:
        logger.exception(f"❌ Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        print(f"Stacktrace:\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
