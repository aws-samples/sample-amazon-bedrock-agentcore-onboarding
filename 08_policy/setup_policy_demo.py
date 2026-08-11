#!/usr/bin/env python3
"""
Prepare the Cedar policy and the demo scopes for Lab 8.

The policy engine and the policy itself are declared in agentcore.json and
created by `agentcore deploy`:

    agentcore add policy-engine --name cost_estimator_policy_engine \
        --attach-to-gateways AWSCostEstimatorGateway --attach-mode ENFORCE
    agentcore add policy --name email_scope_policy \
        --engine cost_estimator_policy_engine --source policies/email_scope.cedar
    agentcore deploy

Two things still need a script:

1. **Rendering the Cedar policy.** The action name and Gateway ARN are only
   known after the Gateway is deployed, so this script reads them from the
   project's deployed state and renders policies/email_scope.cedar from the
   template.
2. **Demo scopes.** To show the policy permitting one caller and denying
   another we need tokens with different scopes. Rather than creating extra app
   clients (which would also have to be added to the Gateway's allowedClients),
   this script adds two scopes to the *existing* M2M client. The caller then
   asks for one scope at a time in the client_credentials request, so the
   client_id — and therefore the Gateway configuration — stays unchanged.

Usage:
    # After `agentcore deploy` created the Gateway in Lab 7
    uv run python setup_policy_demo.py

    # Revert the extra scopes
    uv run python setup_policy_demo.py --cleanup
"""

import argparse
import json
import logging
from pathlib import Path

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

IDENTITY_CONFIG_FILE = Path("../06_identity/inbound_authorizer.json")
CONFIG_FILE = Path("policy_demo.json")
TEMPLATE_FILE = Path("policies/email_scope.cedar.template")
POLICY_FILE = Path("policies/email_scope.cedar")

TARGET_NAME = "AWSCostEstimatorGatewayTarget"
TOOL_NAME = "markdown_to_email"
RESOURCE_SERVER_ID = "agentcore"

# Two demo scopes on the same app client: one matches the Cedar policy, one does not.
DEMO_SCOPES = {
    "manager": {"name": "manager", "description": "Manager scope (permitted by the policy)"},
    "viewer": {"name": "viewer", "description": "Viewer scope (denied by the policy)"},
}
BASE_SCOPE = {"ScopeName": "invoke", "ScopeDescription": "Invoke the runtime"}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    with path.open() as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def load_gateway(project_dir: Path) -> dict:
    """Read the Gateway id and ARN from the CLI's deployed state.

    Reading the file avoids depending on a subprocess: `agentcore status --json`
    would work too, but any Python package that installs a command named
    `agentcore` into the project venv would shadow the npm CLI under `uv run`.
    """
    state_path = project_dir / "agentcore" / ".cli" / "deployed-state.json"
    state = load_json(state_path)

    for target in state.get("targets", {}).values():
        resources = target.get("resources", {})
        # The CLI nests gateways under resources.mcp.gateways; older versions
        # put them directly under resources.gateways.
        for container in (resources, resources.get("mcp", {})):
            gateways = container.get("gateways") or {}
            for name, gateway in gateways.items():
                if gateway.get("gatewayArn"):
                    base_url = (gateway.get("gatewayUrl") or "").rstrip("/")
                    if base_url and not base_url.endswith("/mcp"):
                        base_url = f"{base_url}/mcp"
                    return {
                        "name": name,
                        "id": gateway.get("gatewayId"),
                        "arn": gateway["gatewayArn"],
                        # The MCP endpoint is the base URL plus /mcp
                        "url": base_url,
                    }

    raise ValueError("No deployed gateway found. Run `agentcore deploy` in Lab 7 first.")


def render_policy(gateway_arn: str) -> str:
    """Render policies/email_scope.cedar from the template."""
    template = TEMPLATE_FILE.read_text()
    action_name = f"{TARGET_NAME}___{TOOL_NAME}"
    statement = (
        template
        .replace("__ACTION_NAME__", action_name)
        .replace("__GATEWAY_ARN__", gateway_arn)
    )
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    POLICY_FILE.write_text(statement)
    logger.info("✅ Rendered %s", POLICY_FILE)
    return statement


def set_scopes(cognito, user_pool_id: str, client_id: str, demo: bool) -> list[str]:
    """Declare the resource server scopes and allow them on the app client.

    With demo=True the manager/viewer scopes are added; with demo=False only the
    base invoke scope remains.
    """
    scopes = [BASE_SCOPE]
    if demo:
        for spec in DEMO_SCOPES.values():
            scopes.append({
                "ScopeName": spec["name"],
                "ScopeDescription": spec["description"],
            })

    cognito.update_resource_server(
        UserPoolId=user_pool_id,
        Identifier=RESOURCE_SERVER_ID,
        Name="AgentCore API",
        Scopes=scopes,
    )

    allowed = [f"{RESOURCE_SERVER_ID}/{s['ScopeName']}" for s in scopes]
    # update_user_pool_client replaces the whole configuration, so all the OAuth
    # settings from setup_cognito.py have to be repeated here.
    cognito.update_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=allowed,
        AllowedOAuthFlowsUserPoolClient=True,
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"],
    )
    logger.info("✅ App client allowed scopes: %s", allowed)
    return allowed


def print_next_steps(gateway: dict) -> None:
    print()
    print("=" * 78)
    print("Next steps — run these in the AgentCore project directory")
    print("=" * 78)
    print()
    print("# 1. Policy engine attached to the Gateway in ENFORCE mode")
    print("agentcore add policy-engine \\")
    print("    --name cost_estimator_policy_engine \\")
    print(f"    --attach-to-gateways {gateway['name']} \\")
    print("    --attach-mode ENFORCE")
    print()
    print("# 2. Cedar policy (rendered by this script)")
    print("agentcore add policy \\")
    print("    --name email_scope_policy \\")
    print("    --engine cost_estimator_policy_engine \\")
    print("    --source ../../08_policy/policies/email_scope.cedar")
    print()
    print("# 3. Apply to AWS")
    print("agentcore deploy")
    print()
    print("# 4. Verify: manager is permitted, viewer is denied")
    print("cd ../../08_policy")
    print("uv run python test_policy.py")
    print()
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the Cedar policy and the demo scopes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project-dir",
        default="../agents/MyGatewayProject",
        help="AgentCore project that owns the Gateway",
    )
    parser.add_argument("--cleanup", action="store_true", help="Revert the extra scopes")
    args = parser.parse_args()

    if args.cleanup:
        if not IDENTITY_CONFIG_FILE.exists():
            logger.info("No %s — Cognito was never created, nothing to revert.",
                        IDENTITY_CONFIG_FILE)
        else:
            identity = load_json(IDENTITY_CONFIG_FILE)["cognito"]
            cognito = boto3.client("cognito-idp", region_name=identity["region"])
            set_scopes(cognito, identity["user_pool_id"], identity["client_id"], demo=False)
        for path in (CONFIG_FILE, POLICY_FILE):
            if path.exists():
                path.unlink()
                logger.info("Removed %s", path)
        return 0

    identity = load_json(IDENTITY_CONFIG_FILE)["cognito"]
    cognito = boto3.client("cognito-idp", region_name=identity["region"])

    gateway = load_gateway(Path(args.project_dir))
    logger.info("Gateway: %s (%s)", gateway["name"], gateway["arn"])

    statement = render_policy(gateway["arn"])
    print()
    print("--- policies/email_scope.cedar ---")
    print(statement)

    set_scopes(cognito, identity["user_pool_id"], identity["client_id"], demo=True)

    save_config({
        "gateway": gateway,
        "token_endpoint": identity["token_endpoint"],
        "client_id": identity["client_id"],
        "client_secret": identity["client_secret"],
        "scopes": {
            key: f"{RESOURCE_SERVER_ID}/{spec['name']}"
            for key, spec in DEMO_SCOPES.items()
        },
    })
    logger.info("✅ Saved configuration to %s", CONFIG_FILE)

    print_next_steps(gateway)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
