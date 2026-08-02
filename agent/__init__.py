"""
Nexa Agent — Agent Engine Package (v4.3.0)
==========================================

Sub-organized into 10 category subfolders. All module paths are backwards
compatible — ``agent.<name>`` still resolves through this shim file.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Re-exports (org chart)
# ---------------------------------------------------------------------------
# agent/core/
from .core.conversation_loop import *          # noqa: F401,F403
from .core.iteration_budget import *           # noqa: F401,F403
from .core.message_sanitizer import *         # noqa: F401,F403
from .core.self_health import *               # noqa: F401,F403

# agent/prompt/
from .prompt.prompt_builder import *          # noqa: F401,F403
from .prompt.prompt_expander import *         # noqa: F401,F403
from .prompt.ask_question_mode import *       # noqa: F401,F403

# agent/understanding/
from .understanding.intent_classifier import *      # noqa: F401,F403
from .understanding.pattern_recognizer import *      # noqa: F401,F403
from .understanding.query_reformulator import *     # noqa: F401,F403
from .understanding.proactive_suggester import *    # noqa: F401,F403

# agent/reasoning/
from .reasoning.reasoning_chain import *     # noqa: F401,F403
from .reasoning.confidence_scorer import *   # noqa: F401,F403
from .reasoning.fact_validator import *     # noqa: F401,F403
from .reasoning.response_synthesizer import *  # noqa: F401,F403

# agent/memory/
from .memory.memory_curator import *        # noqa: F401,F403
from .memory.memory_files import *          # noqa: F401,F403
from .memory.memory_consolidator import *   # noqa: F401,F403
from .memory.semantic_memory import *       # noqa: F401,F403
from .memory.session_search import *        # noqa: F401,F403
from .memory.knowledge_cache import *       # noqa: F401,F403

# agent/context/
from .context.context_compressor import *   # noqa: F401,F403
from .context.context_enricher import *     # noqa: F401,F403

# agent/error/
from .error.error_classifier import *       # noqa: F401,F403
from .error.error_memory import *           # noqa: F401,F403
from .error.self_healer import *            # noqa: F401,F403

# agent/learning/
from .learning.learning_graph import *       # noqa: F401,F403
from .learning.autonomous_learner import *  # noqa: F401,F403
from .learning.self_improvement import *    # noqa: F401,F403

# agent/persona/
from .persona.adaptive_persona import *     # noqa: F401,F403
from .persona.persona_manager import *      # noqa: F401,F403
from .persona.orchestrator import *         # noqa: F401,F403

# agent/research/
from .research.deep_research import *       # noqa: F401,F403

# agent/observability/
from .observability.trajectory_recorder import *  # noqa: F401,F403

