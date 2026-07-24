#!/usr/bin/env python3
"""Setup script for AgentCore agent deployment.

Copies agent source code into an agentcore create scaffold and configures
additionalPolicies in agentcore.json. Cross-platform (no jq/cp dependency).

Usage:
    python setup.py --source CostEstimatorAgent --target MyCostEstimatorAgent
"""

import argparse
import json
import shutil
from pathlib import Path


def copy_agent_code(source_dir: Path, target_dir: Path) -> None:
    """Copy agent source code (excluding READMEs) into the target app directory."""
    # Copy Python files and pyproject.toml
    for file in source_dir.glob("*.py"):
        shutil.copy2(file, target_dir / file.name)
    
    pyproject = source_dir / "pyproject.toml"
    if pyproject.exists():
        shutil.copy2(pyproject, target_dir / "pyproject.toml")

    # Copy iam_policies directory
    iam_policies_src = source_dir / "iam_policies"
    if iam_policies_src.exists():
        iam_policies_dst = target_dir / "iam_policies"
        if iam_policies_dst.exists():
            shutil.rmtree(iam_policies_dst)
        shutil.copytree(iam_policies_src, iam_policies_dst)


def configure_additional_policies(agentcore_json_path: Path, policies: list[str]) -> None:
    """Add additionalPolicies to runtimes[0] in agentcore.json."""
    with open(agentcore_json_path, "r") as f:
        config = json.load(f)

    if "runtimes" in config and len(config["runtimes"]) > 0:
        config["runtimes"][0]["additionalPolicies"] = policies

    with open(agentcore_json_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Setup agent code in agentcore scaffold")
    parser.add_argument("--source", required=True, help="Source agent directory name (e.g. CostEstimatorAgent)")
    parser.add_argument("--target", required=True, help="Target scaffold directory name (e.g. MyCostEstimatorAgent)")
    args = parser.parse_args()

    agents_dir = Path(__file__).parent
    source_dir = agents_dir / args.source / "app" / args.source
    target_dir = agents_dir / args.target / "app" / args.target
    agentcore_json = agents_dir / args.target / "agentcore" / "agentcore.json"

    # Validate paths
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return 1
    if not target_dir.exists():
        print(f"❌ Target directory not found: {target_dir}")
        print(f"   Did you run 'agentcore create --name {args.target}' first?")
        return 1
    if not agentcore_json.exists():
        print(f"❌ agentcore.json not found: {agentcore_json}")
        return 1

    # 1. Copy agent code
    print(f"📁 Copying agent code: {source_dir.name} → {target_dir.name}")
    copy_agent_code(source_dir, target_dir)

    # 2. Configure additionalPolicies
    iam_policies_dir = target_dir / "iam_policies"
    if iam_policies_dir.exists():
        policies = [f"iam_policies/{p.name}" for p in sorted(iam_policies_dir.glob("*.json"))]
        print(f"🔧 Configuring additionalPolicies: {policies}")
        configure_additional_policies(agentcore_json, policies)

    print("✅ Setup complete!")
    print(f"\nNext steps:")
    print(f"  cd {args.target}/app/{args.target}")
    print(f"  uv sync")
    print(f"  cd ../..")
    print(f"  agentcore deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
