"""Evaluator that checks whether the agent called required tools.

Success factor: The agent must use pricing API tools to retrieve real data
rather than hallucinating prices from its training data.
"""

import logging

from opentelemetry.sdk.trace import ReadableSpan
from strands_evals.evaluators.evaluator import Evaluator
from strands_evals.types.evaluation import EvaluationData, EvaluationOutput

logger = logging.getLogger(__name__)


class ToolCallEvaluator(Evaluator[str, str]):
    """Check that the agent invoked all required tools during execution.

    Inspects the raw OTel spans captured by the in-memory exporter.
    Tool execution spans have ``gen_ai.operation.name == "execute_tool"``
    and the tool name is stored in ``span.name``.

    Args:
        required_tools: Tool names that must appear in the trajectory.
        min_tool_calls: Minimum number of times *any* required tool must be called.
    """

    def __init__(
        self,
        required_tools: list[str] | None = None,
        min_tool_calls: int = 1,
    ):
        super().__init__()
        self.required_tools = required_tools or ["get_pricing"]
        self.min_tool_calls = min_tool_calls

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        """Evaluate whether all required tools were called."""
        trajectory = evaluation_case.actual_trajectory
        if not trajectory:
            return [
                EvaluationOutput(
                    score=0.0,
                    test_pass=False,
                    reason="No trajectory data available",
                )
            ]

        # Extract tool names from OTel spans
        called_tools: dict[str, int] = {}
        for item in trajectory:
            if not isinstance(item, ReadableSpan):
                continue
            attrs = item.attributes or {}
            operation = attrs.get("gen_ai.operation.name", "")
            if operation == "execute_tool":
                tool_name = attrs.get("gen_ai.tool.name", item.name or "")
                called_tools[tool_name] = called_tools.get(tool_name, 0) + 1

        # Check each required tool
        missing_tools = []
        for tool in self.required_tools:
            count = called_tools.get(tool, 0)
            if count < self.min_tool_calls:
                missing_tools.append(f"{tool} (called {count}x, need {self.min_tool_calls}x)")

        if missing_tools:
            return [
                EvaluationOutput(
                    score=0.0,
                    test_pass=False,
                    reason=f"Missing required tools: {', '.join(missing_tools)}. "
                    f"Tools called: {list(called_tools.keys())}",
                )
            ]

        return [
            EvaluationOutput(
                score=1.0,
                test_pass=True,
                reason=f"All required tools called: {list(called_tools.keys())}",
            )
        ]
