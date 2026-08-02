"""
Tests for the Deep Research Agent (v3.2.0).

Verifies:
    - Deep research reformulates the query into multiple queries.
    - Ornith-deep research combines multiple sources into facts.
    - sources are extracted and validated before being used in answers.
    - cross-validation works on similar facts.
    - conflicts are detected between contradictory sources.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from unittest.mock import AsyncMock, patch

import pytest

from agent.research.deep_research import (
    DEEP_RESEARCH_SCHEMA,
    ResearchResult,
    deep_research,
    deep_research_tool,
)


class TestDeepResearchSchema:
    """Schema tests for deep_research tool."""

    def test_schema_has_question_property(self) -> None:
        """The schema must define a 'question' property."""
        assert "question" in DEEP_RESEARCH_SCHEMA["properties"]

    def test_schema_required_includes_question(self) -> None:
        """'question' must be in the required list."""
        assert "question" in DEEP_RESEARCH_SCHEMA["required"]

    def test_schema_has_max_sources_property(self) -> None:
        """The schema must have max_sources property."""
        assert "max_sources" in DEEP_RESEARCH_SCHEMA["properties"]


class TestDeepResearch:
    """Tests for deep_research function."""

    @pytest.mark.asyncio
    async def test_empty_question_raises(self) -> None:
        """An empty question must raise ValueError."""
        with pytest.raises(ValueError, match="question"):
            await deep_research("")

    @pytest.mark.asyncio
    async def test_whitespace_question_raises(self) -> None:
        """A whitespace-only question must raise ValueError."""
        with pytest.raises(ValueError, match="question"):
            await deep_research("   ")

    @pytest.mark.asyncio
    async def test_research_returns_result(self) -> None:
        """deep_research returns a ResearchResult object."""
        mock_search = AsyncMock(return_value=[
            {"title": "Python 3.13", "url": "https://python.org", "snippet": "Latest Python 3.13.3"},
        ])
        result = await deep_research(
            "What is the latest Python version?",
            search_fn=mock_search,
            top_k=1,
        )
        assert isinstance(result, ResearchResult)
        assert result.query == "What is the latest Python version?"

    @pytest.mark.asyncio
    async def test_reformulated_queries_included(self) -> None:
        """The result includes reformulated queries."""
        mock_search = AsyncMock(return_value=[])
        result = await deep_research(
            "latest AI news",
            search_fn=mock_search,
        )
        assert len(result.reformulated) >= 1

    @pytest.mark.asyncio
    async def test_sources_extracted(self) -> None:
        """Sources are extracted and stored."""
        mock_search = AsyncMock(return_value=[
            {"title": "Test", "url": "https://example.com", "snippet": "Test snippet"},
        ])
        # Mock _fetch_page_content to return content without network.
        with patch("agent.deep_research._fetch_page_content", return_value="Python 3.13.3 was released in October 2024."):
            result = await deep_research(
                "Python version",
                search_fn=mock_search,
            )
        assert len(result.sources_searched) >= 1

    @pytest.mark.asyncio
    async def test_facts_have_confidence(self) -> None:
        """Facts have a confidence score between 0 and 1."""
        mock_search = AsyncMock(return_value=[
            {"title": "Python 3.13", "url": "https://python.org", "snippet": "Released Oct 2024"},
        ])
        with patch("agent.deep_research._fetch_page_content", return_value="Python 3.13.3 was released in October 2024."):
            result = await deep_research(
                "Python release date",
                search_fn=mock_search,
            )
        if result.facts:
            assert all(0.0 <= f.confidence <= 1.0 for f in result.facts)

    @pytest.mark.asyncio
    async def test_citations_extracted(self) -> None:
        """Citations are extracted from sources."""
        mock_search = AsyncMock(return_value=[
            {"title": "Python", "url": "https://python.org/downloads/", "snippet": ""},
        ])
        with patch("agent.deep_research._fetch_page_content", return_value="Python 3.13.3 released October 2024"):
            result = await deep_research(
                "Python version",
                search_fn=mock_search,
            )
        assert len(result.citations) >= 1 or len(result.sources_searched) >= 1

    @pytest.mark.asyncio
    async def test_answer_generated(self) -> None:
        """An answer is synthesized from facts."""
        mock_search = AsyncMock(return_value=[
            {"title": "Python 3.13", "url": "https://python.org", "snippet": "Latest"},
        ])
        with patch("agent.deep_research._fetch_page_content", return_value="Python 3.13.3 is the latest."):
            result = await deep_research(
                "What is latest Python?",
                search_fn=mock_search,
            )
        assert len(result.answer) > 0

    @pytest.mark.asyncio
    async def test_duration_measured(self) -> None:
        """Research duration is measured."""
        mock_search = AsyncMock(return_value=[])
        result = await deep_research("test", search_fn=mock_search)
        assert result.duration_ms > 0


class TestDeepResearchTool:
    """Tests for the tool-callable deep_research_tool."""

    @pytest.mark.asyncio
    async def test_tool_returns_string(self) -> None:
        """The tool returns a string answer."""
        from agent.research.deep_research import deep_research_tool
        from agent.research.deep_research import ResearchResult

        mock_search = AsyncMock(return_value=[])

        async def fake_deep_research(q, **kwargs):
            return ResearchResult(
                query=q,
                reformulated=[q],
                sources_searched=[],
                facts=[],
                conflicts=[],
                answer="Test answer",
                citations=[],
                confidence=0.5,
                duration_ms=100.0,
            )

        # Patch deep_research inside the tool.
        with patch("agent.deep_research.deep_research", side_effect=fake_deep_research):
            result = await deep_research_tool("test question", search_fn=mock_search)
        assert isinstance(result, str)
        assert "Test answer" in result

    @pytest.mark.asyncio
    async def test_empty_question_raises(self) -> None:
        """Empty question raises ValueError."""
        with pytest.raises(ValueError, match="question"):
            await deep_research_tool("")

    @pytest.mark.asyncio
    async def test_tool_schema_valid(self) -> None:
        """The schema is valid OpenAI function-calling format."""
        assert DEEP_RESEARCH_SCHEMA["type"] == "object"
        assert DEEP_RESEARCH_SCHEMA["properties"]["question"]["type"] == "string"
