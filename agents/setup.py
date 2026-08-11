#!/usr/bin/env python3
"""Setup script for AgentCore agent deployment.

Copies the base agent source code into an `agentcore create` scaffold and
configures additionalPolicies in agentcore.json. Cross-platform (no jq/cp
dependency).

Only the base agent (CostEstimatorAgent) lives under agents/. Lab-specific
variations live in the lab directory (for example ../03_memory/agent) and are
layered on top of the base with --overlay.

A project can hold several agents. --target names the project directory and
--agent names the agent inside it; --agent defaults to --target for the common
case where they match.

Usage:
    # Lab 1 / Lab 2 — base agent as-is
    python setup.py --target MyCostEstimatorAgent

    # Lab 3 — base agent + memory overlay
    python setup.py --target MyCostEstimatorAgent --overlay ../03_memory/agent

    # Lab 6 — a second agent inside the same project
    python setup.py --target MyCostEstimatorAgent --agent MySecureAgent \
        --overlay ../06_identity/agent
"""

import argparse
import json
import shutil
from pathlib import Path

BASE_AGENT = "CostEstimatorAgent"


def copy_python_sources(source_dir: Path, target_dir: Path) -> list[str]:
    """Copy *.py and pyproject.toml from source_dir into target_dir."""
    copied = []
    for file in sorted(source_dir.glob("*.py")):
        shutil.copy2(file, target_dir / file.name)
        copied.append(file.name)

    pyproject = source_dir / "pyproject.toml"
    if pyproject.exists():
        shutil.copy2(pyproject, target_dir / "pyproject.toml")
        copied.append("pyproject.toml")

    return copied


def copy_iam_policies(source_dir: Path, target_dir: Path) -> None:
    """Copy the iam_policies directory if the source provides one."""
    iam_policies_src = source_dir / "iam_policies"
    if not iam_policies_src.exists():
        return

    iam_policies_dst = target_dir / "iam_policies"
    if iam_policies_dst.exists():
        shutil.rmtree(iam_policies_dst)
    shutil.copytree(iam_policies_src, iam_policies_dst)


def configure_additional_policies(
    agentcore_json_path: Path, agent_name: str, policies: list[str]
) -> None:
    """Add additionalPolicies to the runtime named agent_name in agentcore.json."""
    with open(agentcore_json_path, "r") as f:
        config = json.load(f)

    for runtime in config.get("runtimes", []):
        if runtime.get("name") == agent_name:
            runtime["additionalPolicies"] = policies
            break

    with open(agentcore_json_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def drop_placeholder_credentials(agentcore_json_path: Path) -> list[str]:
    """Drop credential declarations whose name ends with "undefined".

    `agentcore add agent --protocol MCP` declares an API key credential named
    "<project>undefined": an MCP agent has no model provider, and the fallback
    path in the CLI's write-agent-to-project still derives a credential name from
    that empty value. The credential is never used, so it is removed here to keep
    agentcore.json to the resources the project actually needs.

    This is a no-op when no such declaration exists, so it stays correct if the
    CLI stops emitting one. Anything it cannot interpret is left untouched.
    """

    def is_placeholder(credential: object) -> bool:
        if not isinstance(credential, dict):
            return False
        name = credential.get("name")
        return isinstance(name, str) and name.endswith("undefined")

    try:
        with open(agentcore_json_path, "r") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(config, dict):
        return []

    credentials = config.get("credentials")
    if not isinstance(credentials, list):
        return []

    dropped = [c["name"] for c in credentials if is_placeholder(c)]
    if not dropped:
        return []

    config["credentials"] = [c for c in credentials if not is_placeholder(c)]
    with open(agentcore_json_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    return dropped


def main():
    parser = argparse.ArgumentParser(
        description="Setup agent code in an agentcore create scaffold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target project directory name (e.g. MyCostEstimatorAgent)",
    )
    parser.add_argument(
        "--agent",
        help="Agent name inside the project (default: same as --target). Use this "
             "when a project holds several agents, e.g. --agent MySecureAgent",
    )
    parser.add_argument(
        "--source",
        default=BASE_AGENT,
        help=f"Base agent directory name under agents/ (default: {BASE_AGENT})",
    )
    parser.add_argument(
        "--overlay",
        help="Optional directory of lab-specific code copied over the base "
             "(e.g. ../03_memory/agent)",
    )
    args = parser.parse_args()

    agent_name = args.agent or args.target
    agents_dir = Path(__file__).parent
    source_dir = agents_dir / args.source / "app" / args.source
    target_dir = agents_dir / args.target / "app" / agent_name
    agentcore_json = agents_dir / args.target / "agentcore" / "agentcore.json"

    # Validate paths
    if not source_dir.exists():
        print(f"❌ Base agent not found: {source_dir}")
        return 1
    if not target_dir.exists():
        print(f"❌ Target directory not found: {target_dir}")
        if agent_name == args.target:
            print(f"   Did you run 'agentcore create --name {args.target}' first?")
        else:
            print(f"   Did you run 'agentcore add agent --name {agent_name}' first?")
        return 1
    if not agentcore_json.exists():
        print(f"❌ agentcore.json not found: {agentcore_json}")
        return 1

    overlay_dir = None
    if args.overlay:
        overlay_dir = (agents_dir / args.overlay).resolve()
        if not overlay_dir.exists():
            print(f"❌ Overlay directory not found: {overlay_dir}")
            return 1

    # 1. Copy the base agent
    print(f"📁 Copying base agent: {args.source} → {args.target}/app/{agent_name}")
    copied = copy_python_sources(source_dir, target_dir)
    copy_iam_policies(source_dir, target_dir)
    print(f"   {', '.join(copied)}")

    # 2. Layer the lab-specific overlay on top
    if overlay_dir:
        label = "/".join(overlay_dir.parts[-2:])
        print(f"🧩 Applying overlay: {label}")
        overlaid = copy_python_sources(overlay_dir, target_dir)
        copy_iam_policies(overlay_dir, target_dir)
        print(f"   {', '.join(overlaid)}")

    # 3. Configure additionalPolicies
    iam_policies_dir = target_dir / "iam_policies"
    if iam_policies_dir.exists():
        policies = [f"iam_policies/{p.name}" for p in sorted(iam_policies_dir.glob("*.json"))]
        print(f"🔧 Configuring additionalPolicies: {policies}")
        configure_additional_policies(agentcore_json, agent_name, policies)

    # 4. Tidy up placeholder credentials left by MCP agents
    dropped = drop_placeholder_credentials(agentcore_json)
    if dropped:
        print(f"🧹 Dropped unused credential declarations: {', '.join(dropped)}")

    print("✅ Setup complete!")
    print("\nNext steps:")
    print(f"  cd {args.target}/app/{agent_name}")
    print("  uv sync")
    print("  cd ../..")
    print("  agentcore deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
