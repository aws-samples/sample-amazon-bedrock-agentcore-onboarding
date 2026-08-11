#!/usr/bin/env python3
"""
Clean up the policy resources created in 08_policy.

The policy engine and the Cedar policy live inside Lab 7's project
(agents/MyGatewayProject), so this script removes just those and leaves the
Gateway alone — Lab 7's clean_resources.py handles the Gateway.

Removal order matters: a policy engine cannot be removed while it still holds a
policy.

    agentcore remove policy --engine ... --name ...   # first
    agentcore remove policy-engine --name ...         # then
    agentcore deploy                                  # applies both to AWS

The demo scopes added to the Cognito app client are reverted through
setup_policy_demo.py --cleanup.

Usage:
    uv run python clean_resources.py
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent / "agents" / "MyGatewayProject"
POLICY_ENGINE_NAME = "cost_estimator_policy_engine"
POLICY_NAME = "email_scope_policy"


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


def declared_names(project_dir: Path, key: str) -> list[str]:
    """List the names declared under a key of agentcore.json."""
    config_path = project_dir / "agentcore" / "agentcore.json"
    if not config_path.exists():
        return []
    with config_path.open() as f:
        config = json.load(f)
    return [item.get("name") for item in config.get(key, []) if item.get("name")]


# --- Cognito demo scopes ----------------------------------------------------
def revert_demo_scopes() -> None:
    """Run setup_policy_demo.py --cleanup to restore the original scopes."""
    script = HERE / "setup_policy_demo.py"
    if not script.exists():
        logger.info("No setup_policy_demo.py — skipping scope revert.")
        return
    logger.info("$ python setup_policy_demo.py --cleanup")
    result = subprocess.run(
        [sys.executable, str(script), "--cleanup"],
        cwd=HERE, capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("  ↳ exit %d: %s", result.returncode,
                       (result.stderr or result.stdout).strip()[:300])


# --- Verification -----------------------------------------------------------
def verify() -> bool:
    """Confirm the policy engine is gone."""
    control = boto3.client("bedrock-agentcore-control")
    try:
        engines = [
            e.get("name") or e.get("policyEngineId")
            for e in control.list_policy_engines().get("items", [])
            if POLICY_ENGINE_NAME in (e.get("name") or e.get("policyEngineId") or "")
        ]
    except Exception as e:  # noqa: BLE001 — API shape may differ by version
        logger.info("Could not list policy engines (%s). Check `agentcore status` instead.", e)
        return True

    if engines:
        logger.warning("⚠️ Policy engines still present: %s", engines)
        return False
    logger.info("✅ No %s policy engine remains", POLICY_ENGINE_NAME)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up the policy resources from 08_policy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.parse_args()

    revert_demo_scopes()

    if not project_exists(PROJECT_DIR):
        logger.info("No project at %s — skipping policy removal.", PROJECT_DIR)
        return 0 if verify() else 1

    engines = declared_names(PROJECT_DIR, "policyEngines")
    logger.info("Project: %s", PROJECT_DIR)
    logger.info("Declared policy engines: %s", engines or "(none)")

    if POLICY_ENGINE_NAME not in engines:
        logger.info("Nothing declared — skipping removal.")
        return 0 if verify() else 1

    # Order matters: the engine still holds the policy.
    run_agentcore(
        ["remove", "policy", "--engine", POLICY_ENGINE_NAME, "--name", POLICY_NAME, "-y"],
        PROJECT_DIR,
    )
    run_agentcore(["remove", "policy-engine", "--name", POLICY_ENGINE_NAME, "-y"], PROJECT_DIR)
    run_agentcore(["deploy", "-y"], PROJECT_DIR)

    logger.info("The Gateway is left in place — use 07_gateway/clean_resources.py --force for it.")
    return 0 if verify() else 1


if __name__ == "__main__":
    raise SystemExit(main())
