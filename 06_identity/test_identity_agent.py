"""
Verify inbound and outbound auth on the deployed AgentCore Runtime.

Inbound auth
------------
The Runtime is declared with ``--authorizer-type CUSTOM_JWT``, so AgentCore
validates the caller's JWT before the agent code runs. This script proves it by
invoking twice: once without a token (expect AccessDeniedException) and once
with a Cognito access token (expect success).

boto3's ``invoke_agent_runtime`` has no parameter for a bearer token, so the
token is injected with a ``before-send`` hook, which also skips SigV4 signing.

Outbound auth
-------------
The second invocation asks the agent to add two numbers. The agent cannot do
this itself — it has to call a JWT-protected MCP server. It obtains that token
from AgentCore Identity inside the Runtime, using the credential provider
declared with ``agentcore add credential``. Look for
``Bedrock AgentCore.GetResourceOauth2Token`` in ``agentcore logs`` afterwards.

Usage:
    uv run python test_identity_agent.py
    uv run python test_identity_agent.py --prompt 'What is 17 plus 25? Use the tool.'
"""

import argparse
import json
import logging
import uuid
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_FILE = Path("inbound_authorizer.json")
PROJECT_DIR = Path("../agents/MyCostEstimatorAgent")
AGENT_RUNTIME_NAME = "MySecureAgent"

DEFAULT_PROMPT = "What is 17 plus 25? Use the tool."


def load_cognito() -> dict:
    """Read the Cognito settings written by setup_cognito.py."""
    if not CONFIG_FILE.exists():
        raise SystemExit(
            f"{CONFIG_FILE} not found. Run `uv run python setup_cognito.py` first."
        )
    with CONFIG_FILE.open() as f:
        return json.load(f)["cognito"]


def load_runtime_arn(project_dir: Path, runtime_name: str) -> str:
    """Read a Runtime ARN from agentcore/.cli/deployed-state.json."""
    state_path = project_dir / "agentcore" / ".cli" / "deployed-state.json"
    if not state_path.exists():
        raise SystemExit(
            f"{state_path} not found. Run `agentcore deploy` in the project directory first."
        )
    with state_path.open() as f:
        state = json.load(f)

    for target in state.get("targets", {}).values():
        runtimes = target.get("resources", {}).get("runtimes", {})
        if runtime_name in runtimes:
            return runtimes[runtime_name]["runtimeArn"]

    raise SystemExit(f"Runtime '{runtime_name}' not found. Run `agentcore deploy` first.")


def get_access_token(cognito: dict) -> str:
    """Get a Cognito access token with the client-credentials (M2M) flow.

    This is the caller's side of inbound auth. AgentCore Identity is not
    involved here — the client talks to the authorization server directly.
    """
    token_url = f"https://{cognito['domain']}.auth.{cognito['region']}.amazoncognito.com/oauth2/token"
    response = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": cognito["client_id"],
            "client_secret": cognito["client_secret"],
            "scope": cognito["scope"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    logger.info("✅ Access token obtained (scope: %s)", cognito["scope"])
    return token


def invoke(runtime_arn: str, prompt: str, region: str, bearer_token: str = "") -> str:
    """Invoke the Runtime, optionally with a bearer token.

    For a Runtime with customJWTAuthorizer, AgentCore expects the JWT in an
    `Authorization: Bearer` header instead of SigV4. boto3 has no parameter for
    it, so the header is injected on the wire.
    """
    client = boto3.client("bedrock-agentcore", region_name=region)

    if bearer_token:
        def _inject_bearer(request, **_):
            request.headers["Authorization"] = f"Bearer {bearer_token}"

        client.meta.events.register(
            "before-send.bedrock-agentcore.InvokeAgentRuntime", _inject_bearer
        )

    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
        runtimeSessionId=f"identity-verification-{uuid.uuid4()}",
    )

    chunks = []
    for line in response["response"].iter_lines():
        if not line:
            continue
        text = line.decode("utf-8")
        if text.startswith("data: "):
            chunks.append(json.loads(text[6:]))
    return "".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify inbound and outbound auth on the secured Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send. The agent answers in the prompt's language",
    )
    args = parser.parse_args()

    cognito = load_cognito()
    region = cognito["region"]
    runtime_arn = load_runtime_arn(PROJECT_DIR, AGENT_RUNTIME_NAME)
    logger.info("Runtime ARN: %s", runtime_arn)

    print("=" * 70)
    print("[1] Inbound auth — invoke WITHOUT a token (expect denial)")
    print("=" * 70)
    try:
        invoke(runtime_arn, args.prompt, region)
        print("⚠️ Unexpected success. The Runtime should require a JWT.")
    except ClientError as e:
        print(f"✅ Rejected as expected: {e.response['Error']['Code']}")

    print()
    print("=" * 70)
    print("[2] Inbound auth — invoke WITH a Cognito token")
    print("=" * 70)
    token = get_access_token(cognito)
    result = invoke(runtime_arn, args.prompt, region, bearer_token=token)
    print(result)

    print()
    print("=" * 70)
    print("[3] Outbound auth — how the answer was produced")
    print("=" * 70)
    print("The agent could not add the numbers itself; it called the MCP server.")
    print("To see AgentCore Identity issuing that token, run:")
    print()
    print("  agentcore logs --runtime MySecureAgent --since 10m \\")
    print("    | grep -E 'GetResourceOauth2Token|MCP call'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
