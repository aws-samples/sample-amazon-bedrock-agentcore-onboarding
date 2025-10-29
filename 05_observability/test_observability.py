#!/usr/bin/env python3
"""
AgentCore Observability Test Script

This script demonstrates AgentCore observability capabilities by:
1. Reading agent ARN from .bedrock_agentcore.yaml
2. Using meaningful session IDs (user_id + datetime format)
3. Testing multiple invocations in the same session
4. Intentionally causing errors to test error detection
5. Recording observable logs in CloudWatch for monitoring

Usage:
    python test_observability.py
"""

import json
import logging
import boto3
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from botocore.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ObservabilityTester:
    """Test AgentCore observability with meaningful session tracking"""
    
    def __init__(self, agent_arn: str, region: str = ""):
        self.agent_arn = agent_arn
        self.region = region
        if not self.region:
            # Use default region from boto3 session if not specified
            self.region = boto3.Session().region_name
        config = Config(
            region_name=self.region,
            read_timeout=600 
        )
        self.client = boto3.client('bedrock-agentcore', config=config)
    
    def generate_session_id(self, user_id: str) -> str:
        """Generate meaningful session ID with minimum length requirement"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # AgentCore requires session ID to be at least 16 characters
        session_id = f"{user_id}_{timestamp}_observability_test"
        logger.info(f"Generated session ID: {session_id} (length: {len(session_id)})")
        return session_id
    
    def invoke_agent(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Single agent invocation with error handling"""
        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload).encode('utf-8'),
                traceId=session_id[:128]  # Ensure trace ID is within limit
            )
            
            result = self._process_response(response)
            return {
                'status': 'success',
                'result': result
            }
            
        except Exception as e:
            logger.error(f"❌ Error in invocation: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def test_multiple_invocations_same_session(self, user_id: str) -> Dict[str, Any]:
        """Test multiple invocations in the same session"""
        session_id = self.generate_session_id(user_id)
        
        # Define multiple test prompts
        test_prompts = [
            "I would like to prepare small EC2 for ssh. How much does it cost?",
            "What about the cost for a medium-sized RDS MySQL database?",
            "Can you estimate costs for a simple S3 bucket with 100GB storage?"
        ]
        
        logger.info(f"Testing multiple invocations for user: {user_id}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Number of invocations: {len(test_prompts)}")
        
        results = []
        
        for i, prompt in enumerate(test_prompts, 1):
            logger.info(f"\n--- Invocation {i}/{len(test_prompts)} ---")
            logger.info(f"Prompt: {prompt}")
            
            payload = {"prompt": prompt}
            result = self.invoke_agent(session_id, payload)
            
            result.update({
                'invocation_number': i,
                'prompt': prompt
            })
            results.append(result)
            
            if result['status'] == 'success':
                logger.info(f"✅ Invocation {i} completed successfully")
            else:
                logger.error(f"❌ Invocation {i} failed: {result['error']}")
        
        return {
            'session_id': session_id,
            'user_id': user_id,
            'total_invocations': len(test_prompts),
            'results': results
        }

    
    def _process_response(self, response: Dict[str, Any]) -> str:
        """Process AgentCore runtime response"""
        content = []
        
        if "text/event-stream" in response.get("contentType", ""):
            # Handle streaming response
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        content.append(line)
        
        elif response.get("contentType") == "application/json":
            # Handle JSON response
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))
        
        else:
            content = response.get("response", [])
        
        return ''.join(content)


def load_agent_arn() -> str:
    """Load agent ARN from .bedrock_agentcore.yaml"""
    yaml_path = Path("../02_runtime/.bedrock_agentcore.yaml")
    
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    default_agent = config.get('default_agent')
    if not default_agent:
        raise ValueError("No default_agent specified in configuration")
    
    agent_config = config.get('agents', {}).get(default_agent, {})
    agent_arn = agent_config.get('bedrock_agentcore', {}).get('agent_arn')
    
    if not agent_arn:
        raise ValueError(f"No agent_arn found for agent: {default_agent}")
    
    return agent_arn


def main():
    """Main function to run observability tests"""
    logger.info("🚀 Starting AgentCore Observability Tests")
    
    try:
        # Load agent ARN from configuration
        agent_arn = load_agent_arn()
        logger.info(f"Loaded Agent ARN: {agent_arn}")
        
        # Extract region from ARN
        region = agent_arn.split(':')[3]
        logger.info(f"Region: {region}")
        
        tester = ObservabilityTester(agent_arn, region)
        
        # Test 1: Multiple successful invocations in same session
        logger.info("\n" + "="*60)
        logger.info("Invoke test invocations in Same Session")
        logger.info("="*60)
        tester.test_multiple_invocations_same_session("user0001")
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
