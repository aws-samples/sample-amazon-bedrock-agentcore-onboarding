#!/usr/bin/env python3
"""
AgentCore Observability Test Script

This script demonstrates AgentCore observability capabilities by:
1. Invoking the agent deployed in Lab 2 (02_runtime) multiple times
2. Using meaningful session IDs (user_id + datetime format)
3. Keeping all invocations in the same session so CloudWatch groups them
4. Recording observable traces in CloudWatch for monitoring

The Runtime ARN comes from `agentcore status` — with the AgentCore CLI there is
the CLI writes its deployed state to agentcore/.cli/deployed-state.json.

Usage:
    # Get the ARN from `agentcore status` in the project directory
    uv run python test_observability.py --agent-arn <runtime-arn>

    # Or let the script read it from `agentcore status --json`
    uv run python test_observability.py --project-dir ../agents/MyCostEstimatorAgent
"""

import argparse
import json
import logging

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

import boto3
from botocore.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# The agent answers in the language of the prompt. Override with --prompt to run
# the verification in another language (repeatable).
DEFAULT_PROMPTS = [
    "I would like to prepare small EC2 for ssh. How much does it cost?",
    "What about the cost for a medium-sized RDS MySQL database?",
    "Can you estimate costs for a simple S3 bucket with 100GB storage?",
]


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
        # AgentCore requires runtimeSessionId to be at least 33 characters
        session_id = f"{user_id}_{timestamp}_observability_test"
        logger.info(f"Generated session ID: {session_id} (length: {len(session_id)})")
        return session_id

    def invoke_agent(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Single agent invocation with error handling"""
        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_arn,
                runtimeSessionId=session_id,
                contentType="application/json",
                payload=json.dumps(payload).encode('utf-8'),
                qualifier="DEFAULT",
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

    def test_multiple_invocations_same_session(
        self, user_id: str = "user0001", prompts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Test multiple invocations in the same session"""
        prompts = prompts or DEFAULT_PROMPTS
        session_id = self.generate_session_id(user_id)

        logger.info(f"Testing multiple invocations for user: {user_id}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Number of invocations: {len(prompts)}")

        results = []

        for i, prompt in enumerate(prompts, 1):
            logger.info(f"\n--- Invocation {i}/{len(prompts)} ---")
            logger.info(f"Prompt: {prompt}")

            result = self.invoke_agent(session_id, {"prompt": prompt})

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
            'total_invocations': len(prompts),
            'results': results
        }

    def _process_response(self, response: Dict[str, Any]) -> str:
        """Process AgentCore runtime response.

        The Lab 2 entrypoint streams text deltas, so the Runtime replies with
        Server-Sent Events. Each `data: ` line holds a JSON-encoded string.
        """
        content = []

        if "text/event-stream" in response.get("contentType", ""):
            for line in response["response"].iter_lines(chunk_size=10):
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    content.append(json.loads(decoded[len("data: "):]))

        elif response.get("contentType") == "application/json":
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))

        else:
            content = [str(chunk) for chunk in response.get("response", [])]

        return ''.join(content)


def load_agent_arn_from_state(project_dir: Path) -> Optional[str]:
    """Read the Runtime ARN from the CLI's deployed state.

    `agentcore/.cli/deployed-state.json` is written by `agentcore deploy`.

    Reading the file avoids depending on a subprocess: `agentcore status --json`
    would work too, but any Python package that installs a command named
    `agentcore` into the project venv would shadow the npm CLI under `uv run`.
    """
    state_path = project_dir / "agentcore" / ".cli" / "deployed-state.json"
    if not state_path.exists():
        raise FileNotFoundError(
            f"Deployed state not found: {state_path}. "
            "Run `agentcore deploy` in the project directory first."
        )

    with state_path.open() as f:
        state = json.load(f)

    for target in state.get("targets", {}).values():
        runtimes = target.get("resources", {}).get("runtimes", {})
        for runtime in runtimes.values():
            if runtime.get("runtimeArn"):
                return runtime["runtimeArn"]

    return None


def main() -> int:
    """Main function to run observability tests"""
    parser = argparse.ArgumentParser(
        description="Invoke the deployed agent repeatedly to generate observability data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent-arn", help="Runtime ARN (see `agentcore status`)")
    parser.add_argument(
        "--project-dir",
        help="AgentCore project directory; the ARN is read from agentcore/.cli/deployed-state.json",
    )
    parser.add_argument("--user-id", default="user0001", help="User ID used in the session ID")
    parser.add_argument("--region", default=None, help="AWS region (defaults to the profile)")
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Prompt to send (repeatable). The agent answers in the prompt's language. "
             "Defaults to three English prompts",
    )
    args = parser.parse_args()

    logger.info("🚀 Starting AgentCore Observability Tests")

    try:
        agent_arn = args.agent_arn
        if not agent_arn:
            if not args.project_dir:
                parser.error("Provide either --agent-arn or --project-dir")
            agent_arn = load_agent_arn_from_state(Path(args.project_dir))
            if not agent_arn:
                raise ValueError("No deployed runtime found. Run `agentcore deploy` first.")

        logger.info(f"Loaded Agent ARN: {agent_arn}")

        # Extract region from ARN
        region = args.region or agent_arn.split(':')[3]
        logger.info(f"Region: {region}")

        tester = ObservabilityTester(agent_arn, region)

        logger.info("\n" + "=" * 60)
        logger.info("Invoke test invocations in Same Session")
        logger.info("=" * 60)
        tester.test_multiple_invocations_same_session(args.user_id, args.prompts)

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
