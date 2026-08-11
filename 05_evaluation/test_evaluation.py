"""
Evaluate the AWS Cost Estimator Agent locally

This script runs the agent on your machine and scores it with
strands-agents-evals on two dimensions:

  OutputEvaluator    (built-in) - LLM-as-judge scores the response against a rubric
  ToolCallEvaluator  (custom)   - inspects OTel spans to confirm get_pricing was called

On-demand and online evaluation against the deployed agent are handled by the
AgentCore CLI, so they are not implemented here:

  agentcore add evaluator --config evaluators/tool_usage_evaluator.json ...
  agentcore run eval --runtime <name> --evaluator <name> Builtin.Correctness
  agentcore add online-eval --runtime <name> --evaluator <name> --sampling-rate 100

Usage:
    uv run python test_evaluation.py
    uv run python test_evaluation.py --case single-ec2
"""

import argparse
import logging
import sys
from pathlib import Path

from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import OutputEvaluator

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

# The base agent lives under agents/ and uses flat imports (from config import ...),
# so its directory has to be on sys.path.
AGENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "agents" / "CostEstimatorAgent" / "app" / "CostEstimatorAgent"
)

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


# ---------------------------------------------------------------------------
# Task function: run the cost estimator agent and capture telemetry
# ---------------------------------------------------------------------------
def make_task_fn(telemetry: StrandsEvalsTelemetry):
    """Create a task function that runs the cost estimator and returns spans.

    The returned function clears the in-memory exporter before each run
    to isolate spans per test case.
    """

    def task_fn(case: Case[str, str]) -> dict:
        agent_dir = str(AGENT_DIR)
        if not AGENT_DIR.exists():
            raise FileNotFoundError(
                f"Base agent not found at {AGENT_DIR}. "
                "Clone the repository with agents/CostEstimatorAgent present."
            )
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        from cost_estimator_agent import AWSCostEstimatorAgent

        # Clear previous spans to isolate this test case
        telemetry.in_memory_exporter.clear()

        logger.info("Running cost estimator for case: %s", case.name)
        agent = AWSCostEstimatorAgent()
        try:
            output = agent.estimate_costs(case.input)
        finally:
            agent.cleanup()
        logger.info("Case %s completed, output length: %d chars", case.name, len(output))

        # Collect spans captured during this run
        spans = list(telemetry.in_memory_exporter.get_finished_spans())
        logger.info("Captured %d OTel spans for case: %s", len(spans), case.name)

        return {"output": output, "trajectory": spans}

    return task_fn


def run_local_evaluation(telemetry: StrandsEvalsTelemetry, cases: list[Case]) -> None:
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
        cases=cases,
        evaluators=[output_evaluator, tool_evaluator],
    )
    task_fn = make_task_fn(telemetry)
    reports = experiment.run_evaluations(task_fn)

    for report in reports:
        logger.info("Overall score: %.2f", report.overall_score)
        report.display(include_input=True, include_actual_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the AWS Cost Estimator Agent locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--case",
        action="append",
        help="Run only the named case (repeatable). Default: all cases",
    )
    args = parser.parse_args()

    cases = CASES
    if args.case:
        cases = [c for c in CASES if c.name in args.case]
        if not cases:
            parser.error(f"No matching cases. Available: {[c.name for c in CASES]}")

    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    run_local_evaluation(telemetry, cases)

    logger.info("Evaluation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
