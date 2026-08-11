"""
AWS Cost Estimation Agent with AgentCore Memory

Facade class that encapsulates:
- Model creation (BedrockModel with adaptive retry)
- MCP Pricing client (stdio via uvx, graceful fallback)
- Code Interpreter tool (secure sandbox execution)
- Strands Agent orchestration, one Agent per (session, actor) so that each
  conversation gets its own AgentCore Memory session manager
"""

import logging
import os
import shutil
import boto3
from typing import AsyncGenerator, Optional
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.handlers.callback_handler import null_callback_handler
from strands.agent.conversation_manager.null_conversation_manager import (
    NullConversationManager,
)
from botocore.config import Config
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from config import SYSTEM_PROMPT, DEFAULT_MODEL
from memory_session import get_memory_session_manager

logger = logging.getLogger(__name__)


class AWSCostEstimatorAgent:
    """AWS Cost Estimation Agent — Facade/Singleton.

    Owns the expensive shared resources (model config, MCP pricing client,
    Code Interpreter session) once, and hands out one lightweight Strands
    Agent per (session_id, actor_id) pair. Each Agent is bound to an
    AgentCore Memory session manager, which persists the conversation as
    short-term memory and injects long-term insights back into the context.
    """

    def __init__(self, region: str = ""):
        self.region = region or (
            os.environ.get('AWS_DEFAULT_REGION')
            or os.environ.get('AWS_REGION')
            or boto3.Session().region_name
        )
        self._code_interpreter = None
        self._pricing_client = None
        self._tools = []
        self._agents = {}

        self._initialize()

    def __del__(self):
        """Release resources on garbage collection."""
        self.cleanup()

    def _initialize(self) -> None:
        """Initialize the shared resources used by every session.

        Facade responsibility: builds everything in one place to avoid
        implicit dependencies on external module-level state. Note that the
        Strands Agent itself is NOT built here — it is created per session in
        agent_for() because the memory session manager is session-scoped.
        """
        # 1. Pricing tools (MCP)
        pricing_tools = self._prepare_pricing_tools()

        # 2. Code Interpreter for secure calculations
        self._prepare_code_interpreter()

        # 3. Tool set shared by every session
        self._tools = pricing_tools + [self._prepare_cost_calculation_tool()]

    def agent_for(self, session_id: Optional[str], actor_id: str) -> Agent:
        """Get or create the Agent for a (session, actor) pair.

        The AgentCore Memory session manager restores prior turns of the same
        session (short-term memory) and retrieves actor-scoped insights from
        earlier sessions (long-term memory). NullConversationManager is used
        because history management is delegated to the session manager.
        """
        key = (session_id, actor_id)
        if key not in self._agents:
            self._agents[key] = Agent(
                model=self._load_model(),
                system_prompt=SYSTEM_PROMPT,
                tools=self._tools,
                session_manager=get_memory_session_manager(session_id, actor_id),
                conversation_manager=NullConversationManager(),
            )
        return self._agents[key]

    def _load_model(self) -> BedrockModel:
        """Create BedrockModel with extended timeouts for cost estimation."""
        return BedrockModel(
            boto_client_config=Config(
                read_timeout=900,
                connect_timeout=900,
                retries=dict(max_attempts=3, mode="adaptive"),
            ),
            model_id=DEFAULT_MODEL,
        )

    def _prepare_pricing_tools(self) -> list:
        """Prepare AWS Pricing MCP tools. Returns tool list (may be empty)."""
        try:
            aws_credentials = self._get_aws_credentials()
            env_vars = {"FASTMCP_LOG_LEVEL": "ERROR", **aws_credentials}

            uvx_path = shutil.which("uvx")
            if not uvx_path:
                from uv._find_uv import find_uv_bin
                uv_bin = find_uv_bin()
                uvx_path = os.path.join(os.path.dirname(uv_bin), "uvx")

            uvx_path = self._ensure_executable(uvx_path)

            self._pricing_client = MCPClient(
                lambda: stdio_client(StdioServerParameters(
                    command=uvx_path,
                    args=["awslabs.aws-pricing-mcp-server@latest"],
                    env=env_vars,
                ))
            )
            self._pricing_client.start()
            pricing_tools = self._pricing_client.list_tools_sync()
            logger.info(f"✅ AWS Pricing MCP: {len(pricing_tools)} tools loaded")
            return pricing_tools

        except Exception as e:
            logger.warning(f"⚠️ MCP Pricing tools unavailable: {e}")
            self._pricing_client = None
            return []

    def _prepare_code_interpreter(self) -> None:
        """Start AgentCore Code Interpreter session."""
        try:
            self._code_interpreter = CodeInterpreter(self.region)
            self._code_interpreter.start()
            logger.info("✅ Code Interpreter session started")
        except Exception as e:
            logger.error(f"❌ Failed to setup Code Interpreter: {e}")

    def _prepare_cost_calculation_tool(self):
        """Prepare the Code Interpreter tool bound to this instance."""
        agent_instance = self

        @tool
        def execute_cost_calculation(calculation_code: str, description: str = "") -> str:
            """Execute cost calculations using AgentCore Code Interpreter.

            Args:
                calculation_code: Python code for cost calculations
                description: Description of what the calculation does

            Returns:
                Calculation results as string
            """
            code_interpreter = agent_instance._code_interpreter
            if not code_interpreter:
                return "❌ Code Interpreter not initialized"

            try:
                logger.info(f"🧮 Executing calculation: {description}")
                response = code_interpreter.invoke("executeCode", {
                    "language": "python",
                    "code": calculation_code,
                })

                results = []
                for event in response.get("stream", []):
                    if "result" in event:
                        result = event["result"]
                        if "content" in result:
                            for item in result["content"]:
                                if item.get("type") == "text":
                                    results.append(item["text"])
                return "\n".join(results)

            except Exception as e:
                logger.error(f"❌ Calculation failed: {e}")
                return f"❌ Calculation failed: {e}"

        return execute_cost_calculation

    def _ensure_executable(self, uvx_path: str) -> str:
        """Ensure uvx (and uv) have execute permission.

        On AgentCore Runtime (CodeZip), /var/task is read-only so chmod fails.
        In that case, copy both uv and uvx to /tmp (if not already there) and
        grant execute permission.
        """
        import stat
        import tempfile

        if os.access(uvx_path, os.X_OK):
            return uvx_path

        try:
            os.chmod(uvx_path, os.stat(uvx_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return uvx_path
        except PermissionError:
            pass

        tmp_dir = tempfile.gettempdir()
        tmp_uvx = os.path.join(tmp_dir, "uvx")

        if os.path.exists(tmp_uvx) and os.access(tmp_uvx, os.X_OK):
            logger.info(f"✅ Reusing executable uvx from {tmp_dir}")
            return tmp_uvx

        bin_dir = os.path.dirname(uvx_path)
        for binary in ["uvx", "uv"]:
            src = os.path.join(bin_dir, binary)
            dst = os.path.join(tmp_dir, binary)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                os.chmod(dst, 0o755)

        logger.info(f"✅ Copied uv + uvx to {tmp_dir} with exec permission")
        return tmp_uvx

    def _get_aws_credentials(self) -> dict:
        """Get current AWS credentials including session token."""
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                raise Exception("No AWS credentials found")

            frozen_creds = credentials.get_frozen_credentials()
            creds = {
                "AWS_ACCESS_KEY_ID": frozen_creds.access_key,
                "AWS_SECRET_ACCESS_KEY": frozen_creds.secret_key,
                "AWS_REGION": self.region,
            }
            if frozen_creds.token:
                creds["AWS_SESSION_TOKEN"] = frozen_creds.token
            return creds

        except Exception as e:
            logger.error(f"❌ Failed to get AWS credentials: {e}")
            return {}

    async def stream(
        self, prompt: str, session_id: Optional[str] = None, actor_id: str = "default-user"
    ) -> AsyncGenerator[dict, None]:
        """Stream agent response for a given prompt within a session.

        Yields:
            dict with "data" key containing text chunks
        """
        agent = self.agent_for(session_id, actor_id)
        async for event in agent.stream_async(
            prompt, callback_handler=null_callback_handler
        ):
            yield event

    def cleanup(self) -> None:
        """Release resources."""
        self._agents = {}

        if self._code_interpreter:
            try:
                self._code_interpreter.stop()
            except Exception:
                pass
            self._code_interpreter = None

        if self._pricing_client:
            try:
                self._pricing_client.stop()
            except Exception:
                pass
            self._pricing_client = None
