"""
Nexa Agent — Agent Engine Package (v4.3.0)
==========================================

Sub-organized into 10 category subfolders. Every public name is re-exported
from its new category location so that ``agent.<name>`` imports keep working.

Each subfolder also exports aliases so ``agent.<category>.<module>`` resolves
(e.g. ``from agent.core.conversation_loop import run_conversation``). Existing
code that uses the old flat layout — ``from agent.core.conversation_loop import ...``
— continues to work via the shim modules below.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

# Compatibility: whether or not the shim modules exist on disk, the old flat
# paths (``agent.conversation_loop``, ``agent.memory_curator``, ...) still
# resolve as if the file were at the root. This makes the reorganization
# transparent to importers.

import importlib
import importlib.util
import sys as _sys
from importlib import import_module as _imp

# ----------------------------------------------------------------------
# Module relocation map: flat old name -> new canonical path
# ----------------------------------------------------------------------
_SHIM_MODULE_MAP: dict[str, str] = {
    # core/
    "conversation_loop": "agent.core.conversation_loop",
    "iteration_budget": "agent.core.iteration_budget",
    "message_sanitizer": "agent.core.message_sanitizer",
    "self_health": "agent.core.self_health",
    # prompt/
    "prompt_builder": "agent.prompt.prompt_builder",
    "prompt_expander": "agent.prompt.prompt_expander",
    "ask_question_mode": "agent.prompt.ask_question_mode",
    # understanding/
    "intent_classifier": "agent.understanding.intent_classifier",
    "pattern_recognizer": "agent.understanding.pattern_recognizer",
    "query_reformulator": "agent.understanding.query_reformulator",
    "proactive_suggester": "agent.understanding.proactive_suggester",
    # reasoning/
    "reasoning_chain": "agent.reasoning.reasoning_chain",
    "confidence_scorer": "agent.reasoning.confidence_scorer",
    "fact_validator": "agent.reasoning.fact_validator",
    "response_synthesizer": "agent.reasoning.response_synthesizer",
    # memory/
    "memory_curator": "agent.memory.memory_curator",
    "memory_files": "agent.memory.memory_files",
    "memory_consolidator": "agent.memory.memory_consolidator",
    "semantic_memory": "agent.memory.semantic_memory",
    "session_search": "agent.memory.session_search",
    "knowledge_cache": "agent.memory.knowledge_cache",
    # context/
    "context_compressor": "agent.context.context_compressor",
    "context_enricher": "agent.context.context_enricher",
    # error/
    "error_classifier": "agent.error.error_classifier",
    "error_memory": "agent.error.error_memory",
    "self_healer": "agent.error.self_healer",
    # learning/
    "learning_graph": "agent.learning.learning_graph",
    "autonomous_learner": "agent.learning.autonomous_learner",
    "self_improvement": "agent.learning.self_improvement",
    # persona/
    "adaptive_persona": "agent.persona.adaptive_persona",
    "persona_manager": "agent.persona.persona_manager",
    "orchestrator": "agent.persona.orchestrator",
    # research/
    "deep_research": "agent.research.deep_research",
    # observability/
    "trajectory_recorder": "agent.observability.trajectory_recorder",
}


def _register_shim(old: str, new: str) -> None:
    """Make ``agent.<old>`` an alias that resolves to module ``new``."""
    fq_old = f"agent.{old}"
    if fq_old in _sys.modules:
        return  # don't override an actual submodule
    _sys.modules[fq_old] = _imp(new)


for _old, _new in _SHIM_MODULE_MAP.items():
    try:
        _register_shim(_old, _new)
    except ImportError:
        # If the new location hasn't been created yet (half-migrated tree),
        # don't explode — the import will fall back to the raw module path
        # that's still real.
        pass


# ----------------------------------------------------------------------
# Try to re-export the public API from each submodule for discoverability.
# Wrapped in try/except so a partial refactor doesn't crash the import of
# the package itself.
# ----------------------------------------------------------------------

try:
    from .core.conversation_loop import *  # noqa: F401,F403
except ImportError:
    pass  # subfolder not yet populated


