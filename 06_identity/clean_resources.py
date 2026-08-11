"""
Clean up the identity resources created in 06_identity.

Two kinds of resources are involved:

1. **AgentCore resources** — the JWT-protected agent, the MCP server, and the
   credential provider. Lab 6 adds these to Lab 2's project, so they are removed
   individually rather than with `agentcore remove all`:

       agentcore remove agent --name MySecureAgent
       agentcore remove agent --name MyMcpServer
       agentcore remove credential --name CostEstimatorOutboundIdentity
       agentcore deploy       # applies the removals to AWS

   `agentcore remove all` would also drop Lab 2's agent, which later labs still
   need, so this script never calls it.

2. **Cognito** is outside the CLI's scope and is deleted with boto3 via
   setup_cognito.delete_cognito().

The Cognito user pool is also used by Lab 7 (Gateway) and Lab 8 (Policy) as the
JWT authorizer, so it is kept unless --force is given.

Usage:
    uv run python clean_resources.py            # AgentCore resources only
    uv run python clean_resources.py --force    # also delete Cognito
"""

import argparse
import json
import logging
import shutil
import subprocess
from pathlib import Path

import boto3

import setup_cognito

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent / "agents" / "MyCostEstimatorAgent"
CONFIG_FILE = Path(__file__).resolve().parent / "inbound_authorizer.json"

# Agents and credentials Lab 6 adds to Lab 2's project.
LAB6_AGENTS = ["MySecureAgent", "MyMcpServer"]
LAB6_CREDENTIALS = ["CostEstimatorOutboundIdentity"]
# `add agent --protocol MCP` leaves this stray API key credential behind (CLI 0.25.0).
STRAY_CREDENTIAL = "MyCostEstimatorAgentundefined"
# Runtimes are named <project>_<agent>.
RUNTIME_PREFIXES = [f"MyCostEstimatorAgent_{name}" for name in LAB6_AGENTS]
KEEP_AGENT = "MyCostEstimatorAgent"
POOL_NAME_PREFIX = "agentcore-cost-estimator"


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


def declared_names(project_dir: Path) -> tuple[list[str], list[str]]:
    """Return the agent and credential names declared in agentcore.json."""
    config_path = project_dir / "agentcore" / "agentcore.json"
    with config_path.open() as f:
        config = json.load(f)
    agents = [r.get("name") for r in config.get("runtimes", [])]
    credentials = [c.get("name") for c in config.get("credentials", [])]
    return agents, credentials


def remove_lab6_resources(project_dir: Path) -> bool:
    """Remove only what Lab 6 added, leaving Lab 2's agent in place."""
    agents, credentials = declared_names(project_dir)

    targets = [name for name in LAB6_AGENTS if name in agents]
    cred_targets = [name for name in (*LAB6_CREDENTIALS, STRAY_CREDENTIAL)
                    if name in credentials]

    if not targets and not cred_targets:
        logger.info("Nothing from Lab 6 is declared — nothing to clean.")
        return False

    for name in targets:
        run_agentcore(["remove", "agent", "--name", name, "-y"], project_dir)
    for name in cred_targets:
        run_agentcore(["remove", "credential", "--name", name, "-y"], project_dir)

    run_agentcore(["deploy", "-y"], project_dir)

    # The agent source directories are not touched by `remove agent`.
    for name in targets:
        agent_dir = project_dir / "app" / name
        if agent_dir.exists():
            shutil.rmtree(agent_dir, ignore_errors=True)
            logger.info("Removed %s", agent_dir)

    remaining, _ = declared_names(project_dir)
    if KEEP_AGENT in remaining:
        logger.info("✅ Lab 2's %s is still declared", KEEP_AGENT)
    else:
        logger.warning("⚠️ %s is gone — later labs need it", KEEP_AGENT)
    return True


# --- Cognito ----------------------------------------------------------------
def remove_cognito() -> None:
    """Delete the Cognito user pool created by setup_cognito.py."""
    if not CONFIG_FILE.exists():
        logger.info("No %s — Cognito was never created here.", CONFIG_FILE.name)
        return
    with CONFIG_FILE.open() as f:
        config = json.load(f)
    if "cognito" not in config:
        logger.info("No cognito section in %s.", CONFIG_FILE.name)
        return

    setup_cognito.delete_cognito(config["cognito"])
    CONFIG_FILE.unlink()
    logger.info("Removed %s", CONFIG_FILE.name)


# --- Verification -----------------------------------------------------------
def verify(check_cognito: bool) -> bool:
    """Confirm the Lab 6 runtimes — and optionally Cognito — are gone."""
    ok = True

    control = boto3.client("bedrock-agentcore-control")
    names = [r["agentRuntimeName"]
             for r in control.list_agent_runtimes().get("agentRuntimes", [])]

    for prefix in RUNTIME_PREFIXES:
        found = [n for n in names if n.startswith(prefix)]
        if found:
            logger.warning("⚠️ Runtimes still present: %s", found)
            ok = False
        else:
            logger.info("✅ No %s* runtime remains", prefix)

    if any(n == f"{KEEP_AGENT}_{KEEP_AGENT}" for n in names):
        logger.info("✅ Lab 2's %s_%s runtime is still deployed", KEEP_AGENT, KEEP_AGENT)

    if check_cognito:
        cognito = boto3.client("cognito-idp")
        pools = [
            p["Name"]
            for p in cognito.list_user_pools(MaxResults=60).get("UserPools", [])
            if p["Name"].startswith(POOL_NAME_PREFIX)
        ]
        if pools:
            logger.warning("⚠️ Cognito user pools still present: %s", pools)
            ok = False
        else:
            logger.info("✅ No %s* user pool remains", POOL_NAME_PREFIX)

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up the identity resources from 06_identity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--force", action="store_true",
                        help="Also delete Cognito, which later labs use as the JWT authorizer")
    args = parser.parse_args()

    if project_exists(PROJECT_DIR):
        logger.info("Project: %s", PROJECT_DIR)
        remove_lab6_resources(PROJECT_DIR)
    else:
        logger.info("No project at %s — skipping AgentCore removal.", PROJECT_DIR)

    if args.force:
        remove_cognito()
    else:
        logger.warning("⚠️ Cognito is kept: Lab 7 (Gateway) and Lab 8 (Policy) use it as the")
        logger.warning("   JWT authorizer. Re-run with --force once those labs are done.")

    return 0 if verify(check_cognito=args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())
