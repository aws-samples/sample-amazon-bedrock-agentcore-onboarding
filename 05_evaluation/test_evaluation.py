"""
Evaluate the AWS Cost Estimator Agent

This script measures two dimensions (tool usage + output quality) in three modes:

  Local     (default)    - strands-agents-evals with OutputEvaluator + ToolCallEvaluator
  On-Demand (--ondemand) - AgentCore Evaluation API with Builtin.Correctness
                           + a custom evaluator for tool usage
  Online    (--online)   - Continuous monitoring via online evaluation config
                           + agent invocation on AgentCore Runtime

Usage:
    # Local evaluation (development)
    uv run python test_evaluation.py

    # On-demand evaluation (agent runs locally, scored by AgentCore API)
    uv run python test_evaluation.py --ondemand

    # Online evaluation (agent on Runtime, continuous monitoring)
    uv run python test_evaluation.py --online
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import quote as url_encode

import boto3
import requests
import yaml
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError

from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import OutputEvaluator
from strands_evals.evaluators.evaluator import Evaluator
from strands_evals.types import EvaluationOutput

from evaluators import ToolCallEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# Suppress noisy library loggers
logging.getLogger("strands").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CASES: list[Case[str, str]] = [
    Case(
        name="single-ec2",
        input="One EC2 t3.micro instance running 24/7 in us-east-1",
        expected_output=None,
        expected_trajectory=["get_pricing"],
        metadata={"expected_tools": ["get_pricing", "execute_cost_calculation"]},
    ),
    Case(
        name="multi-service",
        input="Two EC2 m5.large instances with an RDS db.t3.micro in us-east-1",
        expected_output=None,
        expected_trajectory=["get_pricing"],
        metadata={"expected_tools": ["get_pricing", "execute_cost_calculation"]},
    ),
]

COST_ESTIMATE_RUBRIC = """\
Evaluate whether the response provides a useful AWS cost estimate.

Criteria:
- Contains specific dollar amounts (monthly or hourly costs)
- Lists the AWS services mentioned in the input
- Provides a total or summary cost figure
- Costs appear reasonable for the requested services

Score 1.0 if the response meets all criteria.
Score 0.5 if some criteria are met but the estimate is incomplete.
Score 0.0 if no meaningful cost estimate is provided.
"""

ONLINE_CONFIG_NAME = "cost_estimator_online_eval"
RUNTIME_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "02_runtime" / ".bedrock_agentcore.yaml"
)

# ---------------------------------------------------------------------------
# Custom evaluator config for on-demand / online tool-usage assessment
# ---------------------------------------------------------------------------
# Why not Builtin.ToolSelectionAccuracy?
#   That built-in judges each tool call the agent *made*, but when the agent
#   hallucinates (skipping tools entirely) there are zero calls to judge —
#   so it silently passes.  We need a TRACE-level evaluator that can detect
#   the *absence* of pricing tool calls.
TOOL_USAGE_EVALUATOR_NAME = "cost_estimator_tool_usage"

TOOL_USAGE_EVALUATOR_CONFIG = {
    "llmAsAJudge": {
        "modelConfig": {
            "bedrockEvaluatorModelConfig": {
                "modelId": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            }
        },
        "instructions": (
            "You are evaluating whether an AI agent used pricing tools to retrieve "
            "real data instead of hallucinating prices.\n\n"
            "Agent interaction (includes tool calls):\n{context}\n\n"
            "Agent response:\n{assistant_turn}\n\n"
            "Did the agent call a pricing tool (such as get_pricing) to retrieve "
            "real AWS pricing data before producing cost figures?\n"
            "- Score 1 (Yes): The agent called a pricing tool at least once.\n"
            "- Score 0 (No): The agent produced cost figures without calling any "
            "pricing tool, suggesting hallucinated or memorized prices."
        ),
        "ratingScale": {
            "numerical": [
                {"value": 0, "label": "No", "definition": "No pricing tool was called"},
                {"value": 1, "label": "Yes", "definition": "Pricing tool was used"},
            ]
        },
    }
}


def get_or_create_evaluator() -> str:
    """Register a custom evaluator on AgentCore, or reuse an existing one.

    Returns the evaluator ID to pass to create_strands_evaluator().
    """
    control = boto3.client("bedrock-agentcore-control")

    # If the evaluator was already created in a previous run, reuse it
    try:
        resp = control.list_evaluators()
        for ev in resp.get("evaluators", []):
            if ev["evaluatorName"] == TOOL_USAGE_EVALUATOR_NAME:
                logger.info("Reusing existing custom evaluator: %s", ev["evaluatorId"])
                return ev["evaluatorId"]
    except ClientError:
        pass  # fall through to create

    # Create the custom evaluator
    resp = control.create_evaluator(
        evaluatorName=TOOL_USAGE_EVALUATOR_NAME,
        level="TRACE",
        description="Checks whether the agent called pricing tools instead of hallucinating",
        evaluatorConfig=TOOL_USAGE_EVALUATOR_CONFIG,
    )
    evaluator_id = resp["evaluatorId"]
    logger.info("Created custom evaluator: %s (status: %s)", evaluator_id, resp["status"])

    # Wait for the evaluator to become ACTIVE
    for _ in range(30):
        time.sleep(2)
        status = control.get_evaluator(evaluatorId=evaluator_id)["status"]
        if status == "ACTIVE":
            logger.info("Custom evaluator is ACTIVE")
            return evaluator_id
        if "FAILED" in status:
            raise RuntimeError(f"Evaluator creation failed: {status}")
        logger.info("Waiting for evaluator (status: %s)...", status)

    raise TimeoutError(f"Evaluator {evaluator_id} did not become ACTIVE within 60s")


# ---------------------------------------------------------------------------
# Online evaluation: agent config, Runtime invocation, online config
# ---------------------------------------------------------------------------
def load_agent_config() -> dict[str, str]:
    """Load agent configuration from step 02's .bedrock_agentcore.yaml.

    Returns dict with keys: agent_id, agent_arn, region.
    """
    if not RUNTIME_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Runtime config not found at {RUNTIME_CONFIG_PATH}. "
            "Complete step 02 (deploy to AgentCore Runtime) first."
        )
    with open(RUNTIME_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    agent_name = config["default_agent"]
    agent_cfg = config["agents"][agent_name]
    return {
        "agent_id": agent_cfg["bedrock_agentcore"]["agent_id"],
        "agent_arn": agent_cfg["bedrock_agentcore"]["agent_arn"],
        "region": agent_cfg["aws"]["region"],
    }


def invoke_agent_on_runtime(agent_arn: str, region: str, prompt: str) -> str:
    """Invoke the cost estimator agent on AgentCore Runtime via SigV4-authenticated HTTP.

    This follows the same pattern as 02_runtime/test_agentcore_endpoint.py.
    """
    encoded_arn = url_encode(agent_arn, safe="")
    endpoint_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )
    payload = json.dumps({"prompt": prompt})
    content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    session = boto3.Session()
    credentials = session.get_credentials()
    request = AWSRequest(
        method="POST",
        url=endpoint_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-amz-content-sha256": content_hash,
        },
    )
    SigV4Auth(credentials, "bedrock-agentcore", region).add_auth(request)
    prepared = request.prepare()

    logger.info("Invoking agent on Runtime: %s", agent_arn)
    response = requests.post(
        prepared.url,
        data=prepared.body,
        headers=prepared.headers,
        timeout=300,
    )
    response.raise_for_status()

    try:
        body = response.json()
        return body if isinstance(body, str) else json.dumps(body)
    except (json.JSONDecodeError, ValueError):
        return response.text


def get_or_create_online_config(agent_id: str, evaluator_id: str) -> str:
    """Create or reuse an online evaluation config for the cost estimator agent.

    Uses bedrock-agentcore-starter-toolkit which handles IAM execution role
    auto-creation and CloudWatch log group discovery.

    Returns the online evaluation config ID.
    """
    from bedrock_agentcore_starter_toolkit import Evaluation

    eval_client = Evaluation()

    # Check if config already exists
    try:
        configs = eval_client.list_online_configs()
        for cfg in configs:
            if cfg.get("onlineEvaluationConfigName") == ONLINE_CONFIG_NAME:
                config_id = cfg["onlineEvaluationConfigId"]
                logger.info("Reusing existing online eval config: %s", config_id)
                return config_id
    except (ClientError, Exception) as e:
        logger.debug("Could not list online configs: %s", e)

    # Create new config
    logger.info("Creating online evaluation config: %s", ONLINE_CONFIG_NAME)
    resp = eval_client.create_online_config(
        config_name=ONLINE_CONFIG_NAME,
        agent_id=agent_id,
        sampling_rate=100.0,
        evaluator_list=["Builtin.Correctness", evaluator_id],
        config_description=(
            "Online evaluation for cost estimator agent: "
            "Builtin.Correctness + custom tool usage evaluator"
        ),
        auto_create_execution_role=True,
        enable_on_create=True,
    )
    config_id = resp["onlineEvaluationConfigId"]
    logger.info("Created online eval config: %s (status: %s)", config_id, resp.get("status"))
    return config_id


def run_online_evaluation() -> None:
    """Set up online evaluation and invoke agent on Runtime to generate traces."""
    logger.info("=" * 60)
    logger.info("Online Evaluation (continuous monitoring via CloudWatch)")
    logger.info("=" * 60)

    # Step 1: Load agent config from step 02
    agent_config = load_agent_config()
    agent_id = agent_config["agent_id"]
    agent_arn = agent_config["agent_arn"]
    region = agent_config["region"]
    logger.info("Agent ID: %s, Region: %s", agent_id, region)

    # Step 2: Create/reuse custom evaluator
    evaluator_id = get_or_create_evaluator()

    # Step 3: Create/reuse online evaluation config
    config_id = get_or_create_online_config(agent_id, evaluator_id)
    logger.info("Online evaluation config: %s", config_id)

    # Step 4: Invoke agent on Runtime for each test case
    for case in CASES:
        logger.info("Invoking agent on Runtime for case: %s", case.name)
        output = invoke_agent_on_runtime(agent_arn, region, case.input)
        logger.info("Case %s completed, output length: %d chars", case.name, len(output))
        preview = output[:200] + "..." if len(output) > 200 else output
        logger.info("Output preview: %s", preview)

    # Step 5: Print instructions for viewing results
    console_url = (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home"
        f"?region={region}#container-insights:infrastructure/bedrock-agentcore"
    )
    logger.info("=" * 60)
    logger.info("Online evaluation is active.")
    logger.info("Config: %s (%s)", ONLINE_CONFIG_NAME, config_id)
    logger.info("Traces are being evaluated automatically in CloudWatch.")
    logger.info("View results: %s", console_url)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Task function: run the cost estimator agent and capture telemetry
# ---------------------------------------------------------------------------
def make_task_fn(telemetry: StrandsEvalsTelemetry):
    """Create a task function that runs the cost estimator and returns spans.

    The returned function clears the in-memory exporter before each run
    to isolate spans per test case.
    """

    def task_fn(case: Case[str, str]) -> dict:
        # Add parent directory to path so we can import the agent
        agent_dir = str(Path(__file__).resolve().parent.parent / "01_code_interpreter")
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent

        # Clear previous spans to isolate this test case
        telemetry.in_memory_exporter.clear()

        logger.info("Running cost estimator for case: %s", case.name)
        agent = AWSCostEstimatorAgent()
        output = agent.estimate_costs(case.input)
        logger.info("Case %s completed, output length: %d chars", case.name, len(output))

        # Collect spans captured during this run
        spans = list(telemetry.in_memory_exporter.get_finished_spans())
        logger.info("Captured %d OTel spans for case: %s", len(spans), case.name)

        return {"output": output, "trajectory": spans}

    return task_fn


def run_local_evaluation(telemetry: StrandsEvalsTelemetry) -> None:
    """Evaluate with local evaluators: output quality + tool usage."""
    logger.info("=" * 60)
    logger.info("Local Evaluation (OutputEvaluator + ToolCallEvaluator)")
    logger.info("=" * 60)

    output_evaluator = OutputEvaluator(rubric=COST_ESTIMATE_RUBRIC)
    tool_evaluator = ToolCallEvaluator(
        required_tools=["get_pricing"],
        min_tool_calls=1,
    )

    experiment = Experiment(
        cases=CASES,
        evaluators=[output_evaluator, tool_evaluator],
    )
    task_fn = make_task_fn(telemetry)
    reports = experiment.run_evaluations(task_fn)

    for report in reports:
        logger.info("Overall score: %.2f", report.overall_score)
        report.display(include_input=True, include_actual_output=True)


class AgentCoreEvaluator(Evaluator[str, str]):
    """Evaluate agent output using AgentCore Evaluation API.

    Calls the Evaluate API directly via boto3 instead of using the SDK's
    create_strands_evaluator(), which references a non-existent service name
    ('agentcore-evaluation-dataplane').  The Evaluate API lives on the
    'bedrock-agentcore' service.

    See: https://github.com/aws/bedrock-agentcore-sdk-python/issues/266
    """

    def __init__(self, evaluator_id: str, test_pass_score: float = 0.7):
        super().__init__()
        self.evaluator_id = evaluator_id
        self.test_pass_score = test_pass_score
        self.client = boto3.client("bedrock-agentcore")

    def evaluate(self, evaluation_case):
        from bedrock_agentcore.evaluation.span_to_adot_serializer import (
            convert_strands_to_adot,
        )

        trajectory = evaluation_case.actual_trajectory
        if not trajectory:
            return [EvaluationOutput(score=0.0, test_pass=False, reason="No trajectory data")]

        # Convert raw OTel spans to ADOT format if needed
        if not (isinstance(trajectory[0], dict) and "scope" in trajectory[0]):
            trajectory = convert_strands_to_adot(trajectory)

        response = self.client.evaluate(
            evaluatorId=self.evaluator_id,
            evaluationInput={"sessionSpans": trajectory},
        )
        return [
            EvaluationOutput(
                score=r.get("value", 0.0),
                test_pass=r.get("value", 0.0) >= self.test_pass_score,
                reason=r.get("explanation", ""),
            )
            for r in response["evaluationResults"]
        ]


def run_ondemand_evaluation(telemetry: StrandsEvalsTelemetry) -> None:
    """On-demand evaluation: agent runs locally, scored by AgentCore Evaluate API."""
    logger.info("=" * 60)
    logger.info("On-Demand Evaluation (AgentCore Evaluation API)")
    logger.info("=" * 60)

    # Output quality — same dimension as local OutputEvaluator
    correctness = AgentCoreEvaluator("Builtin.Correctness", test_pass_score=0.7)
    # Tool usage — custom evaluator (same dimension as local ToolCallEvaluator)
    # We register a TRACE-level LLM-as-judge that checks whether pricing tools
    # were called.  Unlike Builtin.ToolSelectionAccuracy, this catches the case
    # where the agent makes *zero* tool calls (the hallucination scenario).
    evaluator_id = get_or_create_evaluator()
    tool_usage = AgentCoreEvaluator(evaluator_id, test_pass_score=0.7)

    experiment = Experiment(
        cases=CASES,
        evaluators=[correctness, tool_usage],
    )
    task_fn = make_task_fn(telemetry)
    reports = experiment.run_evaluations(task_fn)

    for report in reports:
        logger.info("Overall score: %.2f", report.overall_score)
        report.display(include_input=True, include_actual_output=True)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the AWS Cost Estimator Agent"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--ondemand",
        action="store_true",
        help="On-demand evaluation: agent runs locally, scored by AgentCore Evaluate API",
    )
    group.add_argument(
        "--online",
        action="store_true",
        help="Online evaluation: set up continuous monitoring and invoke agent on Runtime",
    )
    args = parser.parse_args()

    if args.online:
        # Online mode: agent runs on Runtime, no local telemetry needed
        run_online_evaluation()
    else:
        # Local and on-demand both need in-memory telemetry
        telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
        if args.ondemand:
            run_ondemand_evaluation(telemetry)
        else:
            run_local_evaluation(telemetry)

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    main()
