#!/usr/bin/env python3
"""
Clean up the gateway resources created in 07_gateway.

Two kinds of resources are involved:

1. **AgentCore resources** (Gateway, target, credential — plus the policy engine
   if Lab 8 was run) live in agents/MyGatewayProject and are removed with the CLI:

       agentcore remove all   # empties the declarations in agentcore.json
       agentcore deploy       # applies the removal to AWS

2. **The Lambda function** was deployed with AWS SAM, so its CloudFormation
   stack is deleted directly.

Lab 8 (Policy) attaches a policy engine to this Gateway and its Cedar policy
embeds the Gateway ARN, so this script refuses to delete unless --force is given.

Usage:
    uv run python clean_resources.py            # check and warn
    uv run python clean_resources.py --force    # actually delete
"""

import argparse
import json
import logging
import shutil
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent / "agents" / "MyGatewayProject"
LAMBDA_STACK_NAME = "AWS-Cost-Estimator-Tool-Markdown-To-Email"
GATEWAY_PREFIX = "mygatewayproject"


# --- AgentCore CLI helpers ---------------------------------------------------
def run_agentcore(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run the AgentCore CLI in cwd and report the outcome."""
    logger.info("$ agentcore %s", " ".join(args))
    result = subprocess.run(["agentcore", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("  ↳ exit %d: %s", result.returncode,
                       (result.stderr or result.stdout).strip()[:300])
    return result


def project_exists(project_dir: Path) -> bool:
    return (project_dir / "agentcore" / "agentcore.json").exists()


def deployed_resources(project_dir: Path) -> dict:
    """Read agentcore/.cli/deployed-state.json (written by agentcore deploy)."""
    state_path = project_dir / "agentcore" / ".cli" / "deployed-state.json"
    if not state_path.exists():
        return {}
    with state_path.open() as f:
        state = json.load(f)
    for target in state.get("targets", {}).values():
        return target.get("resources", {})
    return {}


def remove_project(project_dir: Path, delete_dir: bool = True) -> None:
    """Remove every AgentCore resource in the project, then apply it to AWS."""
    run_agentcore(["remove", "all", "-y"], project_dir)
    run_agentcore(["deploy", "-y"], project_dir)
    if delete_dir:
        shutil.rmtree(project_dir, ignore_errors=True)
        logger.info("Removed %s", project_dir)


# --- Lambda (AWS SAM) -------------------------------------------------------
def remove_lambda_stack() -> None:
    """Delete the CloudFormation stack created by deploy.sh (AWS SAM)."""
    cfn = boto3.client("cloudformation")
    try:
        cfn.describe_stacks(StackName=LAMBDA_STACK_NAME)
    except ClientError:
        logger.info("Lambda stack %s not found — nothing to delete.", LAMBDA_STACK_NAME)
        return

    logger.info("Deleting Lambda stack %s...", LAMBDA_STACK_NAME)
    cfn.delete_stack(StackName=LAMBDA_STACK_NAME)
    logger.info("Delete requested. It completes asynchronously.")


# --- Verification -----------------------------------------------------------
def verify() -> bool:
    """Confirm the gateway is gone.

    The Gateway's ``name`` keeps the project's casing
    (``MyGatewayProject-AWSCostEstimatorGateway``); only ``gatewayId`` is
    lower-cased. Matching on the id avoids a false "already gone" result.
    """
    control = boto3.client("bedrock-agentcore-control")
    gateways = [
        g.get("name") or g.get("gatewayId")
        for g in control.list_gateways().get("items", [])
        if GATEWAY_PREFIX in g.get("gatewayId", "").lower()
    ]
    if gateways:
        logger.warning("⚠️ Gateways still present: %s", gateways)
        return False
    logger.info("✅ No %s* gateway remains", GATEWAY_PREFIX)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up the gateway resources from 07_gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--force", action="store_true",
                        help="Delete even though Lab 8 (Policy) uses this gateway")
    parser.add_argument("--keep-lambda", action="store_true",
                        help="Keep the SAM-deployed Lambda stack")
    args = parser.parse_args()

    if not project_exists(PROJECT_DIR):
        logger.info("No project at %s — skipping AgentCore removal.", PROJECT_DIR)
        if args.force and not args.keep_lambda:
            remove_lambda_stack()
        return 0 if verify() else 1

    resources = deployed_resources(PROJECT_DIR)
    logger.info("Project: %s", PROJECT_DIR)
    logger.info("Deployed resources: %s", list(resources.keys()) or "(none)")

    if not args.force:
        logger.warning("⚠️ Lab 8 (Policy) attaches a policy engine to this Gateway, and its")
        logger.warning("   Cedar policy embeds the Gateway ARN. Deleting the Gateway makes")
        logger.warning("   Lab 8 impossible to run.")
        logger.warning("   Re-run with --force to delete it anyway.")
        return 0

    remove_project(PROJECT_DIR)
    if not args.keep_lambda:
        remove_lambda_stack()

    logger.info("Cognito is left in place — use 06_identity/clean_resources.py --force for it.")
    return 0 if verify() else 1


if __name__ == "__main__":
    raise SystemExit(main())
