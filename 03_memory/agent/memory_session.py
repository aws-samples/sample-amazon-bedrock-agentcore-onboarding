"""AgentCore Memory wiring for the cost estimator agent.

The Memory resource is declared in ``agentcore/agentcore.json`` under
``memories[]``. ``agentcore deploy`` creates it and injects its ID into the
runtime as an environment variable named ``MEMORY_<MEMORYNAME>_ID``.

Rather than hard-coding that env var name (it depends on the memory name
chosen at ``agentcore create`` time), this module discovers it at runtime so
the same code works for any project name.
"""

import logging
import os
import uuid
from typing import Optional

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

logger = logging.getLogger(__name__)


def resolve_memory_id() -> Optional[str]:
    """Resolve the Memory ID injected by ``agentcore deploy``.

    Looks for an explicit ``AGENTCORE_MEMORY_ID`` override first, then falls
    back to the ``MEMORY_<NAME>_ID`` convention used by the AgentCore CLI.
    """
    explicit = os.environ.get("AGENTCORE_MEMORY_ID")
    if explicit:
        return explicit

    for key, value in os.environ.items():
        if key.startswith("MEMORY_") and key.endswith("_ID") and value:
            logger.info(f"✅ Resolved Memory ID from {key}")
            return value

    return None


def get_memory_session_manager(
    session_id: Optional[str], actor_id: str
) -> Optional[AgentCoreMemorySessionManager]:
    """Build a session manager that reads and writes AgentCore Memory.

    The namespaces below MUST match the ``namespaceTemplates`` declared in
    ``agentcore.json``, because ``agentcore deploy`` grants
    ``RetrieveMemoryRecords`` with an IAM condition on exactly those templates.
    Retrieving from any other namespace — including an EPISODIC strategy's
    ``reflectionNamespaceTemplates`` — fails with AccessDeniedException.

    Only actor-scoped namespaces are retrieved so that insights carry over
    between sessions; session-scoped namespaces would be empty in a new
    session.

    Returns None when no Memory is configured, in which case the agent runs
    without memory instead of failing.
    """
    memory_id = resolve_memory_id()
    if not memory_id:
        logger.warning("⚠️ Memory not configured — running without memory")
        return None

    # AgentCoreMemoryConfig rejects None; synthesize a session when the caller
    # did not provide one (for example a local invocation without a session).
    session_id = session_id or uuid.uuid4().hex

    # relevance_score is a floor on the semantic search score. Extracted
    # preferences typically score around 0.4, so the scaffold default of 0.5
    # filters everything out — 0.3 keeps them while still dropping noise.
    retrieval_config = {
        # SEMANTIC — facts confirmed during past conversations
        f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.3),
        # USER_PREFERENCE — architecture and cost preferences
        f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.3),
    }

    logger.info(
        f"🧠 Memory session manager: memory_id={memory_id} "
        f"actor_id={actor_id} session_id={session_id}"
    )

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
            # Required because the entrypoint streams with stream_async()
            async_mode=True,
        ),
        os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    )
