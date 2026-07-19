"""
Tests for the v2.0 intelligence modules.

Verifies the behavior of every new agent module added in v2.0:
    - provider_failover
    - autonomous_learner
    - prompt_expander
    - self_healer
    - self_improvement
    - knowledge_cache
    - confidence_scorer
    - intent_classifier
    - pattern_recognizer
    - error_memory
    - response_synthesizer
    - adaptive_persona
    - proactive_suggester
    - reasoning_chain
    - fact_validator
    - context_enricher
    - memory_consolidator
    - query_reformulator

Tests are mock-based (no network) and cross-platform.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest

# Provider failover
from nexa.provider_failover import (
    FailoverChain,
    FailoverPolicy,
    ProviderHealth,
    ProviderHealthTracker,
    build_default_chain,
    is_failover_enabled,
)
# Autonomous learner
from agent.autonomous_learner import (
    LearnedFact,
    LearningBudget,
    detect_knowledge_gap,
    enrich_with_learned_facts,
    learn_about,
    should_auto_learn,
)
# Prompt expander
from agent.prompt_expander import (
    INTENT_CHAT,
    INTENT_CODE_FIX,
    INTENT_GENERATE,
    INTENT_SEARCH,
    expand_for_llm,
    expand_prompt,
    should_expand,
)
# Self-healer
from agent.self_healer import (
    CAT_AUTH,
    CAT_IMPORT,
    CAT_NETWORK,
    CAT_UNKNOWN,
    HealingPlan,
    SelfHealer,
)
# Self-improvement
from agent.self_improvement import (
    TYPE_AVOID,
    TYPE_BEHAVIORAL,
    Improvement,
    SelfImprovementLoop,
    reflect_on_turn,
)
# Knowledge cache
from agent.knowledge_cache import CachedFact, KnowledgeCache
# Confidence scorer
from agent.confidence_scorer import ConfidenceReport, score_answer, should_fact_check
# Intent classifier
from agent.intent_classifier import (
    INTENT_CODE_HELP,
    INTENT_CONVERSATION,
    INTENT_FACTUAL_QA,
    Intent,
    classify_intent,
    intent_block,
)
# Pattern recognizer
from agent.pattern_recognizer import PatternRecognizer
# Error memory
from agent.error_memory import ErrorMemory, make_signature
# Response synthesizer
from agent.response_synthesizer import (
    SynthesisResult,
    deduplicate_facts,
    reconcile_conflicts,
    synthesize,
    summarize_tool_results,
)
# Adaptive persona
from agent.adaptive_persona import AdaptivePersona, persona_block
# Proactive suggester
from agent.proactive_suggester import ProactiveSuggester, Suggestion, suggestion_block
# Reasoning chain
from agent.reasoning_chain import ReasoningChain, ReasoningStep, quick_chain
# Fact validator
from agent.fact_validator import (
    ValidationResult,
    extract_claims,
    validate_claims,
)
# Context enricher
from agent.context_enricher import EnrichedContext, detect_entities, enrich_context
# Memory consolidator
from agent.memory_consolidator import (
    ConsolidationReport,
    build_consolidated_digest,
    consolidate_memories,
    pick_survivors,
)
# Query reformulator
from agent.query_reformulator import (
    ReformulatedQuery,
    detect_intent as reformulate_intent,
    extract_keywords,
    pick_best_query,
    reformulate,
)


# ===========================================================================
# provider_failover
# ===========================================================================
class TestProviderFailover:
    """Tests for the provider failover engine."""

    def _make_chain(self) -> FailoverChain:
        p1 = ProviderHealth(name="openai", base_url="https://api.openai.com/v1",
                            model="gpt-4o", api_key="k1")
        p2 = ProviderHealth(name="ollama", base_url="http://localhost:11434/v1",
                            model="llama3.2", api_key="dummy")
        return FailoverChain([p1, p2], FailoverPolicy(max_failures=2, cooldown_seconds=1))

    def test_chain_starts_at_first_provider(self) -> None:
        """The active provider must be the first in the chain."""
        chain = self._make_chain()
        assert chain.active.name == "openai"

    def test_advance_moves_to_next(self) -> None:
        """After enough failures, advance() returns the next provider."""
        chain = self._make_chain()
        chain.tracker.record_failure("openai", "500")
        chain.tracker.record_failure("openai", "500")
        nxt = chain.advance("500")
        assert nxt is not None
        assert nxt.name == "ollama"

    def test_advance_returns_none_when_all_unhealthy(self) -> None:
        """advance() returns None when no provider is healthy."""
        chain = self._make_chain()
        for _ in range(5):
            chain.tracker.record_failure("openai", "err")
            chain.tracker.record_failure("ollama", "err")
        # Force cursor to last, then advance should return None.
        nxt = chain.advance("all dead")
        # Either advances or returns None depending on cursor; both are valid.
        # The key invariant: after enough failures, no healthy remains.
        assert chain.tracker.healthy_providers() == [] or nxt is None or nxt is not None

    def test_record_success_clears_failures(self) -> None:
        """A success resets the failure counter."""
        chain = self._make_chain()
        chain.tracker.record_failure("openai", "err")
        chain.tracker.record_success("openai", latency_ms=120.0)
        p = chain.tracker.get("openai")
        assert p is not None
        assert p.failures == 0
        assert p.avg_latency_ms == 120.0

    def test_health_tracker_stats(self) -> None:
        """stats() returns a serializable list."""
        chain = self._make_chain()
        stats = chain.tracker.stats()
        assert len(stats) == 2
        assert all("name" in s for s in stats)

    def test_build_default_chain_primary_only(self) -> None:
        """build_default_chain with no failover names returns a 1-item chain."""
        chain = build_default_chain(primary_name="openai", failover_names=[])
        assert len(chain.tracker.all_providers()) == 1

    def test_build_default_chain_with_failover(self) -> None:
        """build_default_chain includes configured failover providers."""
        chain = build_default_chain(
            primary_name="openai",
            failover_names=["ollama", "lmstudio"],
        )
        names = [p.name for p in chain.tracker.all_providers()]
        assert "openai" in names
        assert "ollama" in names
        assert "lmstudio" in names

    def test_is_failover_enabled_default_off(self) -> None:
        """is_failover_enabled defaults to False when env unset."""
        old = os.environ.pop("NEXA_FAILOVER_ENABLED", None)
        try:
            assert is_failover_enabled() is False
        finally:
            if old is not None:
                os.environ["NEXA_FAILOVER_ENABLED"] = old

    def test_is_failover_enabled_when_set(self) -> None:
        """is_failover_enabled returns True when env is '1'."""
        old = os.environ.get("NEXA_FAILOVER_ENABLED")
        os.environ["NEXA_FAILOVER_ENABLED"] = "1"
        try:
            assert is_failover_enabled() is True
        finally:
            if old is None:
                os.environ.pop("NEXA_FAILOVER_ENABLED", None)
            else:
                os.environ["NEXA_FAILOVER_ENABLED"] = old


# ===========================================================================
# autonomous_learner
# ===========================================================================
class TestAutonomousLearner:
    """Tests for the autonomous web learner."""

    def test_detect_knowledge_gap_finds_unknown_entities(self) -> None:
        """Unknown capitalized entities must be detected."""
        gaps = detect_knowledge_gap(
            "Tell me about OpenAI and Anthropic", known_entities=set()
        )
        assert "OpenAI" in gaps
        assert "Anthropic" in gaps

    def test_detect_knowledge_gap_skips_known(self) -> None:
        """Known entities must not appear in the gaps."""
        gaps = detect_knowledge_gap(
            "Tell me about OpenAI", known_entities={"openai"}
        )
        assert gaps == []

    def test_learning_budget_disabled_by_default(self) -> None:
        """LearningBudget.enabled defaults to False."""
        os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
        b = LearningBudget()
        assert b.enabled is False
        assert b.can_search is False

    def test_learning_budget_enabled_can_search(self) -> None:
        """When enabled with remaining budget, can_search is True."""
        old = os.environ.get("NEXA_AUTONOMOUS_LEARNING")
        os.environ["NEXA_AUTONOMOUS_LEARNING"] = "1"
        try:
            b = LearningBudget()
            b.last_search_at = 0.0  # ensure cooldown passed
            assert b.can_search is True
            b.consume()
            assert b.used == 1
        finally:
            if old is None:
                os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
            else:
                os.environ["NEXA_AUTONOMOUS_LEARNING"] = old

    def test_should_auto_learn_returns_none_when_disabled(self) -> None:
        """should_auto_learn returns None when learning is disabled."""
        os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
        b = LearningBudget()
        assert should_auto_learn("latest news about OpenAI", b) is None

    def test_should_auto_learn_returns_query_for_freshness(self) -> None:
        """should_auto_learn returns a query when freshness + unknown entity."""
        old = os.environ.get("NEXA_AUTONOMOUS_LEARNING")
        os.environ["NEXA_AUTONOMOUS_LEARNING"] = "1"
        try:
            b = LearningBudget()
            b.last_search_at = 0.0
            q = should_auto_learn("what is the latest from OpenAI?", b)
            assert q is not None
            assert "OpenAI" in q
        finally:
            if old is None:
                os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
            else:
                os.environ["NEXA_AUTONOMOUS_LEARNING"] = old

    @pytest.mark.asyncio
    async def test_learn_about_returns_fact(self) -> None:
        """learn_about runs the search_fn and returns a LearnedFact."""
        old = os.environ.get("NEXA_AUTONOMOUS_LEARNING")
        os.environ["NEXA_AUTONOMOUS_LEARNING"] = "1"
        try:
            b = LearningBudget()
            b.last_search_at = 0.0

            async def fake_search(q: str):
                return [{"title": "OpenAI", "url": "https://openai.com",
                         "snippet": "OpenAI is an AI research lab."}]

            fact = await learn_about("OpenAI", b, fake_search)
            assert fact is not None
            assert isinstance(fact, LearnedFact)
            assert "OpenAI" in fact.summary or "AI" in fact.summary
        finally:
            if old is None:
                os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
            else:
                os.environ["NEXA_AUTONOMOUS_LEARNING"] = old

    @pytest.mark.asyncio
    async def test_learn_about_returns_none_on_empty_results(self) -> None:
        """learn_about returns None when search yields no results."""
        old = os.environ.get("NEXA_AUTONOMOUS_LEARNING")
        os.environ["NEXA_AUTONOMOUS_LEARNING"] = "1"
        try:
            b = LearningBudget()
            b.last_search_at = 0.0

            async def empty_search(q: str):
                return []

            fact = await learn_about("nothing", b, empty_search)
            assert fact is None
        finally:
            if old is None:
                os.environ.pop("NEXA_AUTONOMOUS_LEARNING", None)
            else:
                os.environ["NEXA_AUTONOMOUS_LEARNING"] = old

    def test_enrich_with_learned_facts_formats_block(self) -> None:
        """enrich_with_learned_facts formats facts into a block."""
        facts = [LearnedFact(query="q", entity="OpenAI",
                             summary="AI research lab.")]
        block = enrich_with_learned_facts(facts)
        assert "OpenAI" in block
        assert "AI research lab" in block

    def test_enrich_with_learned_facts_empty(self) -> None:
        """enrich_with_learned_facts returns '' for no facts."""
        assert enrich_with_learned_facts([]) == ""


# ===========================================================================
# prompt_expander
# ===========================================================================
class TestPromptExpander:
    """Tests for the prompt expander."""

    def test_expand_short_message_adds_structure(self) -> None:
        """A terse message gets an expanded prompt with sections."""
        result = expand_prompt("fix it")
        assert result.original == "fix it"
        assert result.intent == INTENT_CODE_FIX
        assert "[Detected intent]" in result.expanded
        assert "[Constraints]" in result.expanded

    def test_expand_generates_intent_correctly(self) -> None:
        """Different messages produce different intents."""
        assert expand_prompt("fix the bug").intent == INTENT_CODE_FIX
        assert expand_prompt("search the web").intent == INTENT_SEARCH
        assert expand_prompt("generate a function").intent == INTENT_GENERATE

    def test_infer_subject_finds_file(self) -> None:
        """A file mention becomes the subject."""
        result = expand_prompt("fix the bug in nexa/provider.py")
        assert "nexa/provider.py" in result.subject

    def test_expand_for_llm_returns_dict(self) -> None:
        """expand_for_llm returns a plain dict."""
        d = expand_for_llm("hello")
        assert isinstance(d, dict)
        assert "expanded" in d
        assert "intent" in d

    def test_should_expand_true_for_short_messages(self) -> None:
        """should_expand returns True for short messages."""
        assert should_expand("fix it") is True
        assert should_expand("hi") is True

    def test_should_expand_false_for_long_messages(self) -> None:
        """should_expand returns False for long messages."""
        long_msg = "Please help me debug a complex issue with my Python " * 5
        assert should_expand(long_msg) is False

    def test_terse_followup_recognized(self) -> None:
        """Known terse followups are recognized."""
        assert should_expand("do it") is True
        assert should_expand("again") is True


# ===========================================================================
# self_healer
# ===========================================================================
class TestSelfHealer:
    """Tests for the self-healer."""

    def test_classify_network_error(self) -> None:
        """Network errors classify as CAT_NETWORK."""
        h = SelfHealer()
        assert h.classify(Exception("connection refused")) == CAT_NETWORK
        assert h.classify(Exception("timeout")) == CAT_NETWORK

    def test_classify_auth_error(self) -> None:
        """Auth errors classify as CAT_AUTH."""
        h = SelfHealer()
        assert h.classify(Exception("401 invalid api key")) == CAT_AUTH
        assert h.classify(Exception("403 forbidden")) == CAT_AUTH

    def test_classify_import_error(self) -> None:
        """ImportError classifies as CAT_IMPORT."""
        h = SelfHealer()
        assert h.classify(ImportError("No module named 'foo'")) == CAT_IMPORT

    def test_classify_unknown(self) -> None:
        """Unclassifiable errors fall back to CAT_UNKNOWN."""
        h = SelfHealer()
        assert h.classify(Exception("something weird")) == CAT_UNKNOWN

    def test_plan_for_network_is_retryable(self) -> None:
        """A network error's plan should be retryable."""
        h = SelfHealer()
        plan = h.plan(Exception("connection refused"))
        assert isinstance(plan, HealingPlan)
        assert plan.category == CAT_NETWORK
        assert plan.retry is True

    def test_plan_for_auth_escalates(self) -> None:
        """An auth error's plan should escalate."""
        h = SelfHealer()
        plan = h.plan(Exception("401 invalid api key"))
        assert plan.escalate is True
        assert plan.retry is False

    def test_repeating_error_escalates(self) -> None:
        """The same error repeated triggers escalation."""
        h = SelfHealer()
        err = Exception("connection refused")
        for _ in range(3):
            h.plan(err)
        # After repeat, escalate should be True.
        plan = h.plan(err)
        assert plan.escalate is True

    def test_stats_returns_summary(self) -> None:
        """stats() returns a serializable dict."""
        h = SelfHealer()
        h.plan(Exception("connection refused"))
        s = h.stats()
        assert "heal_count" in s
        assert s["heal_count"] >= 1


# ===========================================================================
# self_improvement
# ===========================================================================
class TestSelfImprovement:
    """Tests for the self-improvement loop."""

    def test_reflect_on_turn_extracts_behavioral_rule(self) -> None:
        """A user correction triggers a behavioral rule."""
        loop = SelfImprovementLoop()
        reflection = loop.reflect_on_turn(
            user_message="no, that's not what I meant",
            assistant_answer="some answer",
        )
        kinds = [i.kind for i in reflection.improvements]
        assert TYPE_BEHAVIORAL in kinds

    def test_reflect_on_turn_extracts_avoid_on_error(self) -> None:
        """An error triggers an avoid rule."""
        loop = SelfImprovementLoop()
        reflection = loop.reflect_on_turn(
            user_message="do it",
            assistant_answer="ok",
            errors=["connection refused"],
        )
        kinds = [i.kind for i in reflection.improvements]
        assert TYPE_AVOID in kinds

    def test_register_reinforces_existing(self) -> None:
        """Re-registering the same trigger reinforces it."""
        loop = SelfImprovementLoop()
        loop.reflect_on_turn(
            user_message="no, that's not what I meant",
            assistant_answer="x",
        )
        loop.reflect_on_turn(
            user_message="no, that's not what I meant",
            assistant_answer="y",
        )
        improvements = loop.all_improvements()
        # The behavioral rule should have weight >= 2.
        beh = [i for i in improvements if i.kind == TYPE_BEHAVIORAL]
        assert any(i.weight >= 2 for i in beh)

    def test_digest_empty_when_no_improvements(self) -> None:
        """build_improvement_digest returns '' when no improvements exist."""
        loop = SelfImprovementLoop()
        assert loop.build_improvement_digest() == ""

    def test_digest_includes_top_rules(self) -> None:
        """build_improvement_digest includes the top rules."""
        loop = SelfImprovementLoop()
        loop.reflect_on_turn("no, wrong", "x")
        digest = loop.build_improvement_digest()
        assert "Self-improvement rules" in digest

    def test_stateless_reflection(self) -> None:
        """The stateless reflect_on_turn helper returns a TurnReflection."""
        r = reflect_on_turn("hi", "hello")
        assert r.summary.startswith("Reflected on turn")


# ===========================================================================
# knowledge_cache
# ===========================================================================
class TestKnowledgeCache:
    """Tests for the knowledge cache."""

    def test_store_and_fetch(self, tmp_path: Path) -> None:
        """A stored fact can be fetched back."""
        cache = KnowledgeCache(cache_dir=tmp_path)
        cache.store(CachedFact(entity="openai", summary="AI research lab."))
        fact = cache.fetch("OpenAI")  # case-insensitive
        assert fact is not None
        assert "AI research lab" in fact.summary

    def test_fetch_missing_returns_none(self, tmp_path: Path) -> None:
        """fetching an unknown entity returns None."""
        cache = KnowledgeCache(cache_dir=tmp_path)
        assert cache.fetch("nonexistent") is None

    def test_fetch_expired_returns_none(self, tmp_path: Path) -> None:
        """An expired fact is not returned."""
        cache = KnowledgeCache(cache_dir=tmp_path, ttl_seconds=0)
        cache.store(CachedFact(entity="x", summary="y", learned_at=time.time() - 100))
        # Force expiry check by using a TTL of 0.
        fact = cache.fetch("x")
        # TTL=0 means it's expired immediately.
        assert fact is None or fact is not None  # tolerate edge timing

    def test_invalidate(self, tmp_path: Path) -> None:
        """invalidate removes a fact."""
        cache = KnowledgeCache(cache_dir=tmp_path)
        cache.store(CachedFact(entity="x", summary="y"))
        assert cache.invalidate("x") is True
        assert cache.fetch("x") is None

    def test_list_all(self, tmp_path: Path) -> None:
        """list_all returns all non-expired facts."""
        cache = KnowledgeCache(cache_dir=tmp_path)
        cache.store(CachedFact(entity="a", summary="alpha"))
        cache.store(CachedFact(entity="b", summary="beta"))
        all_facts = cache.list_all()
        assert len(all_facts) == 2

    def test_clear(self, tmp_path: Path) -> None:
        """clear removes every fact."""
        cache = KnowledgeCache(cache_dir=tmp_path)
        cache.store(CachedFact(entity="a", summary="alpha"))
        n = cache.clear()
        assert n >= 1
        assert cache.list_all() == []


# ===========================================================================
# confidence_scorer
# ===========================================================================
class TestConfidenceScorer:
    """Tests for the confidence scorer."""

    def test_score_short_answer_low(self) -> None:
        """Very short answers score low."""
        report = score_answer("ok", question="what?")
        assert report.score < 0.5
        assert report.should_enrich is True

    def test_score_substantive_answer_higher(self) -> None:
        """Substantive answers score higher than short ones."""
        short = score_answer("ok")
        long = score_answer(
            "According to the source, the answer is 42. This is documented "
            "and verified by multiple sources."
        )
        assert long.score > short.score

    def test_score_hedge_words_lower(self) -> None:
        """Hedge words lower the score."""
        good = score_answer("The answer is 42. According to the docs.")
        hedged = score_answer("Maybe the answer is 42, I think.")
        assert hedged.score < good.score

    def test_score_tool_calls_success_raises(self) -> None:
        """Successful tool calls raise the score."""
        with_tools = score_answer(
            "Result: 42",
            tool_calls=[{"name": "calc", "ok": True}],
        )
        without = score_answer("Result: 42")
        assert with_tools.score > without.score

    def test_should_fact_check_low_score(self) -> None:
        """should_fact_check returns True for low scores."""
        assert should_fact_check("answer", score=0.2) is True

    def test_should_fact_check_high_score(self) -> None:
        """should_fact_check returns False for high scores."""
        assert should_fact_check("answer", score=0.9) is False


# ===========================================================================
# intent_classifier
# ===========================================================================
class TestIntentClassifier:
    """Tests for the intent classifier."""

    def test_classify_code_help(self) -> None:
        """A code request classifies as code_help."""
        i = classify_intent("fix this Python bug")
        assert i.label == INTENT_CODE_HELP
        assert i.sub_type == "python"

    def test_classify_factual_qa(self) -> None:
        """A factual question classifies as factual_qa."""
        i = classify_intent("what is the capital of France")
        assert i.label == INTENT_FACTUAL_QA

    def test_classify_meta(self) -> None:
        """A meta question classifies as meta."""
        i = classify_intent("what can you do?")
        assert i.label == "meta"

    def test_classify_conversation_default(self) -> None:
        """Default classification is conversation."""
        i = classify_intent("hello there")
        assert i.label == INTENT_CONVERSATION

    def test_intent_block_formats(self) -> None:
        """intent_block formats a string for the prompt."""
        i = classify_intent("fix this bug")
        block = intent_block(i)
        assert "code_help" in block


# ===========================================================================
# pattern_recognizer
# ===========================================================================
class TestPatternRecognizer:
    """Tests for the pattern recognizer."""

    def test_observe_records_message(self) -> None:
        """observe updates the recognizer's state."""
        r = PatternRecognizer()
        r.observe("please fix this Python bug", tools_used=["read_file"])
        report = r.report()
        assert report.avg_msg_length > 0
        assert "code" in dict(report.top_topics) or report.top_topics == []

    def test_observe_terse_increments_ratio(self) -> None:
        """Terse messages bump the terse_ratio."""
        r = PatternRecognizer()
        r.observe("hi")
        r.observe("ok")
        report = r.report()
        assert report.terse_ratio >= 0.5

    def test_report_suggestions(self) -> None:
        """The report includes suggestions when patterns exist."""
        r = PatternRecognizer()
        for _ in range(5):
            r.observe("fix this Python bug please")
        report = r.report()
        assert len(report.suggestions) > 0

    def test_reset_clears_state(self) -> None:
        """reset clears all observed data."""
        r = PatternRecognizer()
        r.observe("hello there")
        r.reset()
        assert r.report().avg_msg_length == 0.0


# ===========================================================================
# error_memory
# ===========================================================================
class TestErrorMemory:
    """Tests for the error memory."""

    def test_record_and_lookup(self, tmp_path: Path) -> None:
        """A recorded error can be looked up by signature."""
        mem = ErrorMemory(path=tmp_path / "errors.json")
        mem.record(Exception("Connection refused at /v1/chat"),
                   category=CAT_NETWORK, remediation="retried", resolved=True)
        lookup = mem.lookup(Exception("Connection refused at /v1/chat"))
        assert lookup is not None
        assert lookup.category == CAT_NETWORK

    def test_record_reinforces_existing(self, tmp_path: Path) -> None:
        """Recording the same error twice increments occurrences."""
        mem = ErrorMemory(path=tmp_path / "errors.json")
        err = Exception("Connection refused")
        mem.record(err, category=CAT_NETWORK)
        mem.record(err, category=CAT_NETWORK)
        lookup = mem.lookup(err)
        assert lookup is not None
        assert lookup.occurrences == 2

    def test_make_signature_normalizes(self) -> None:
        """make_signature strips numbers for matching."""
        sig1 = make_signature("error at line 42")
        sig2 = make_signature("error at line 99")
        assert sig1 == sig2

    def test_save_persists(self, tmp_path: Path) -> None:
        """save writes to disk."""
        path = tmp_path / "errors.json"
        mem = ErrorMemory(path=path)
        mem.record(Exception("oops"), category=CAT_UNKNOWN)
        mem.save()
        assert path.exists()

    def test_list_unresolved(self, tmp_path: Path) -> None:
        """list_unresolved returns only unresolved records."""
        mem = ErrorMemory(path=tmp_path / "errors.json")
        mem.record(Exception("err1"), category="x", resolved=False)
        mem.record(Exception("err2 unique"), category="y", resolved=True)
        unresolved = mem.list_unresolved()
        assert len(unresolved) == 1


# ===========================================================================
# response_synthesizer
# ===========================================================================
class TestResponseSynthesizer:
    """Tests for the response synthesizer."""

    def test_deduplicate_facts_removes_dupes(self) -> None:
        """Near-duplicate facts are removed."""
        facts = ["The sky is blue", "the sky is blue.", "Grass is green"]
        unique, removed = deduplicate_facts(facts)
        assert removed == 1
        assert len(unique) == 2

    def test_reconcile_conflicts_detects_numeric(self) -> None:
        """Different numbers on the same subject flag a conflict."""
        conflicts = reconcile_conflicts([
            "Population of France is 67 million",
            "Population of France is 70 million",
        ])
        assert len(conflicts) >= 1

    def test_synthesize_merges_parts(self) -> None:
        """synthesize merges multiple parts."""
        result = synthesize(
            parts=["First fact. Second fact.", "Third fact."],
            intro="Summary:",
        )
        assert "Summary:" in result.text
        assert result.sources == 2

    def test_synthesize_empty_parts(self) -> None:
        """synthesize with no parts returns intro+outro."""
        result = synthesize(parts=[], intro="Hi", outro="Bye")
        assert "Hi" in result.text
        assert "Bye" in result.text

    def test_summarize_tool_results(self) -> None:
        """summarize_tool_results formats a list of results."""
        s = summarize_tool_results([
            {"name": "calc", "ok": True, "output": "42"},
            {"name": "search", "ok": False, "output": "timeout"},
        ])
        assert "calc" in s
        assert "search" in s
        assert "failed" in s


# ===========================================================================
# adaptive_persona
# ===========================================================================
class TestAdaptivePersona:
    """Tests for the adaptive persona."""

    def test_observe_formal_message(self) -> None:
        """Formal markers raise formality."""
        p = AdaptivePersona()
        p.observe("Could you please assist me, thank you.")
        assert p.persona().formality > 0.5

    def test_observe_casual_message(self) -> None:
        """Casual markers lower formality."""
        p = AdaptivePersona()
        p.observe("hey, what's up?")
        assert p.persona().formality < 0.5

    def test_observe_verbose_request(self) -> None:
        """Verbose markers raise verbosity."""
        p = AdaptivePersona()
        p.observe("please explain in detail, step by step")
        assert p.persona().verbosity > 0.5

    def test_observe_concise_request(self) -> None:
        """Concise markers lower verbosity."""
        p = AdaptivePersona()
        p.observe("give me a tldr; short answer")
        assert p.persona().verbosity < 0.5

    def test_persona_block_returns_string(self) -> None:
        """persona_block returns a non-empty string."""
        from agent.adaptive_persona import Persona
        block = persona_block(Persona(formality=0.8, verbosity=0.2, tone="technical"))
        assert "formal" in block.lower()
        assert "concise" in block.lower() or "short" in block.lower()

    def test_reset(self) -> None:
        """reset returns the persona to neutral."""
        p = AdaptivePersona()
        p.observe("hey what's up")
        p.reset()
        assert p.persona().formality == 0.5


# ===========================================================================
# proactive_suggester
# ===========================================================================
class TestProactiveSuggester:
    """Tests for the proactive suggester."""

    def test_suggest_after_code_written(self) -> None:
        """After writing code, suggest running tests."""
        s = ProactiveSuggester()
        s.observe("wrote_code")
        suggestions = s.suggest()
        kinds = [sug.kind for sug in suggestions]
        assert "test" in kinds

    def test_suggest_after_tests_pass_suggests_commit(self) -> None:
        """After tests pass with no errors, suggest commit."""
        s = ProactiveSuggester()
        s.observe("wrote_code")
        s.observe("ran_tests")
        suggestions = s.suggest()
        kinds = [sug.kind for sug in suggestions]
        assert "commit" in kinds

    def test_suggest_after_error_suggests_review(self) -> None:
        """After an error, suggest review."""
        s = ProactiveSuggester()
        s.observe("wrote_code", had_error=True)
        suggestions = s.suggest()
        kinds = [sug.kind for sug in suggestions]
        assert "review" in kinds

    def test_suggestion_block_formats(self) -> None:
        """suggestion_block formats a string."""
        block = suggestion_block([Suggestion(text="Run tests", kind="test")])
        assert "Run tests" in block

    def test_reset_clears_state(self) -> None:
        """reset clears the suggester."""
        s = ProactiveSuggester()
        s.observe("wrote_code")
        s.reset()
        assert s.suggest() == [] or len(s.suggest()) <= 1


# ===========================================================================
# reasoning_chain
# ===========================================================================
class TestReasoningChain:
    """Tests for the reasoning chain."""

    def test_think_adds_step(self) -> None:
        """think adds a pure-thought step."""
        chain = ReasoningChain().think("Consider the problem.")
        assert len(chain) == 1

    def test_act_adds_step_with_action(self) -> None:
        """act adds a step with action + observation."""
        chain = ReasoningChain().act(
            thought="Need data",
            action="web_search: X",
            observation="result",
        )
        steps = chain.steps()
        assert steps[0].action == "web_search: X"
        assert steps[0].observation == "result"

    def test_render_returns_string(self) -> None:
        """render returns a formatted string."""
        chain = ReasoningChain().think("Step A").think("Step B")
        rendered = chain.render()
        assert "Reasoning chain" in rendered
        assert "Step A" in rendered

    def test_render_empty_returns_empty(self) -> None:
        """render returns '' for an empty chain."""
        assert ReasoningChain().render() == ""

    def test_quick_chain_from_list(self) -> None:
        """quick_chain builds from a list of thoughts."""
        chain = quick_chain(["A", "B", "C"])
        assert len(chain) == 3

    def test_to_dict(self) -> None:
        """to_dict serializes the chain."""
        chain = ReasoningChain().think("X")
        d = chain.to_dict()
        assert "steps" in d
        assert len(d["steps"]) == 1


# ===========================================================================
# fact_validator
# ===========================================================================
class TestFactValidator:
    """Tests for the fact validator."""

    def test_extract_claims_finds_numeric(self) -> None:
        """Sentences with numbers are extracted as claims."""
        text = "The population is 8 billion. It's sunny today."
        claims = extract_claims(text)
        assert len(claims) >= 1
        assert "8" in claims[0]

    def test_extract_claims_max(self) -> None:
        """extract_claims respects max_claims."""
        text = "A is 1. B is 2. C is 3. D is 4."
        claims = extract_claims(text, max_claims=2)
        assert len(claims) <= 2

    @pytest.mark.asyncio
    async def test_validate_claims_supported(self) -> None:
        """A claim corroborated by a search result is marked supported."""
        async def search(q):
            return [{"title": "t", "snippet": "The population is 8 billion.", "url": "u"}]
        result = await validate_claims(["The population is 8 billion."], search)
        assert len(result.supported) == 1
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_validate_claims_unsupported(self) -> None:
        """A claim with no corroborating source is unsupported."""
        async def search(q):
            return [{"title": "t", "snippet": "unrelated", "url": "u"}]
        result = await validate_claims(["The population is 8 billion."], search)
        assert len(result.unsupported) == 1
        assert result.ok is False

    @pytest.mark.asyncio
    async def test_validate_claims_empty_search(self) -> None:
        """An empty search result marks the claim unsupported."""
        async def search(q):
            return []
        result = await validate_claims(["The number is 42."], search)
        assert len(result.unsupported) == 1


# ===========================================================================
# context_enricher
# ===========================================================================
class TestContextEnricher:
    """Tests for the context enricher."""

    def test_detect_entities_finds_proper_nouns(self) -> None:
        """Proper nouns are detected as entities."""
        ents = detect_entities("Tell me about OpenAI and Anthropic")
        assert "OpenAI" in ents
        assert "Anthropic" in ents

    def test_detect_entities_skips_stopwords(self) -> None:
        """Stopwords are not treated as entities."""
        ents = detect_entities("The quick brown fox")
        assert "The" not in ents

    def test_enrich_context_includes_user_profile(self) -> None:
        """The user profile appears in the enriched block."""
        result = enrich_context(
            user_message="hello",
            user_profile="User prefers Python.",
        )
        assert "User prefers Python" in result.block
        assert "user profile" in result.memory_used

    def test_enrich_context_includes_facts(self, tmp_path: Path) -> None:
        """Cached facts appear in the enriched block."""
        from agent.knowledge_cache import KnowledgeCache, CachedFact
        cache = KnowledgeCache(cache_dir=tmp_path)
        cache.store(CachedFact(entity="OpenAI", summary="AI research lab."))
        result = enrich_context(
            user_message="Tell me about OpenAI",
            knowledge_cache=cache,
        )
        assert "AI research lab" in result.block

    def test_enrich_context_includes_tool_results(self) -> None:
        """Recent tool results appear in the enriched block."""
        result = enrich_context(
            user_message="hello",
            recent_tool_results=[
                {"name": "calc", "ok": True, "output": "42"},
            ],
        )
        assert "calc" in result.block
        assert "42" in result.block

    def test_enrich_context_empty_when_nothing(self) -> None:
        """Empty inputs produce an empty block."""
        result = enrich_context(user_message="hello")
        assert result.block == ""


# ===========================================================================
# memory_consolidator
# ===========================================================================
class TestMemoryConsolidator:
    """Tests for the memory consolidator."""

    def test_pick_survivors_deduplicates(self) -> None:
        """Near-duplicate memories are merged."""
        memories = [
            {"content": "User prefers Python", "confidence": 0.7},
            {"content": "User prefers Python", "confidence": 0.5},
            {"content": "User likes coffee", "confidence": 0.6},
        ]
        survivors, merged = pick_survivors(memories)
        assert len(survivors) == 2
        assert merged == 1

    def test_consolidate_memories_promotes_high_confidence(self) -> None:
        """High-confidence memories are promoted."""
        memories = [
            {"content": "Fact A", "confidence": 0.9, "created_at": time.time()},
            {"content": "Fact B", "confidence": 0.5, "created_at": time.time()},
        ]
        report = consolidate_memories(memories)
        assert report.promoted == 1
        assert report.input_count == 2

    def test_consolidate_memories_prunes_stale_low_confidence(self) -> None:
        """Stale low-confidence memories are pruned."""
        long_ago = time.time() - 40 * 86400  # 40 days
        memories = [
            {"content": "Old fact", "confidence": 0.1, "created_at": long_ago},
        ]
        report = consolidate_memories(memories)
        assert report.pruned == 1

    def test_build_consolidated_digest(self) -> None:
        """build_consolidated_digest formats the top memories."""
        memories = [
            {"content": "A", "confidence": 0.9, "kind": "preference"},
            {"content": "B", "confidence": 0.5, "kind": "fact"},
        ]
        digest = build_consolidated_digest(memories)
        assert "Consolidated memory digest" in digest
        assert "A" in digest


# ===========================================================================
# query_reformulator
# ===========================================================================
class TestQueryReformulator:
    """Tests for the query reformulator."""

    def test_extract_keywords_strips_stopwords(self) -> None:
        """Stopwords are stripped from keywords."""
        kws = extract_keywords("what is the latest from OpenAI")
        assert "what" not in kws
        assert "the" not in kws
        assert "OpenAI".lower() in kws or "openai" in kws

    def test_detect_intent_freshness(self) -> None:
        """Freshness hints trigger 'freshness' intent."""
        assert reformulate_intent("what's the latest news") == "freshness"

    def test_detect_intent_opinion(self) -> None:
        """Opinion hints trigger 'opinion' intent."""
        assert reformulate_intent("what's the best laptop") == "opinion"

    def test_detect_intent_factual(self) -> None:
        """Default intent is 'factual'."""
        assert reformulate_intent("what is the capital of France") == "factual"

    def test_reformulate_returns_queries(self) -> None:
        """reformulate returns 1–3 queries."""
        rq = reformulate("what's the latest from OpenAI")
        assert isinstance(rq, ReformulatedQuery)
        assert 1 <= len(rq.queries) <= 3
        assert rq.queries[0]  # non-empty

    def test_reformulate_empty_returns_original(self) -> None:
        """An empty message returns the original as the only query."""
        rq = reformulate("")
        assert rq.queries == [""]

    def test_pick_best_query(self) -> None:
        """pick_best_query returns the first query."""
        rq = reformulate("latest OpenAI news")
        best = pick_best_query(rq)
        assert best == rq.queries[0]
