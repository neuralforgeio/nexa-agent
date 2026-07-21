"""
Tests for SYSTEMPROMPT.md and the extended LICENSE.

Verifies:
    - SYSTEMPROMPT.md exists and has all required sections.
    - The creator "Dearly Febriano Irwansyah" is mentioned (with Indonesian origin).
    - No "Hermes" attribution (research-only reference).
    - LICENSE has the standard MIT core + extended terms (attribution, trademark,
      patent disclaimer, contribution license, AI acknowledgment, Indonesian
      copyright law).
    - LICENSE mentions the creator and Indonesia.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(filename: str) -> str:
    """Read a repo-root file as UTF-8 text."""
    return (REPO_ROOT / filename).read_text(encoding="utf-8")


class TestSystemPrompt:
    """Tests for SYSTEMPROMPT.md."""

    def test_file_exists(self) -> None:
        """SYSTEMPROMPT.md must exist."""
        assert (REPO_ROOT / "SYSTEMPROMPT.md").exists()

    def test_has_identity_section(self) -> None:
        """The prompt has an Identity section."""
        content = _read("SYSTEMPROMPT.md")
        assert "IDENTITY" in content.upper()

    def test_mentions_creator_name(self) -> None:
        """The prompt mentions the creator's name."""
        content = _read("SYSTEMPROMPT.md")
        assert "Dearly Febriano Irwansyah" in content

    def test_mentions_indonesia(self) -> None:
        """The prompt mentions Indonesia as the creator's origin."""
        content = _read("SYSTEMPROMPT.md")
        assert "Indonesia" in content or "Indonesian" in content

    def test_mentions_mit_license(self) -> None:
        """The prompt mentions the MIT License."""
        content = _read("SYSTEMPROMPT.md")
        assert "MIT" in content

    def test_has_behavioral_rules(self) -> None:
        """The prompt has a Behavioral Rules section."""
        content = _read("SYSTEMPROMPT.md")
        assert "BEHAVIORAL RULES" in content.upper() or "BEHAVIORAL" in content.upper()

    def test_has_tools_catalog(self) -> None:
        """The prompt lists the available tools."""
        content = _read("SYSTEMPROMPT.md")
        # At least 3 tools must be mentioned.
        tool_mentions = sum(1 for t in ("read_file", "write_file", "run_terminal_command",
                                         "web_search", "code_execution", "delegate")
                            if t in content)
        assert tool_mentions >= 3

    def test_has_memory_protocol(self) -> None:
        """The prompt has a Memory Protocol section."""
        content = _read("SYSTEMPROMPT.md")
        assert "MEMORY" in content.upper() and "PROTOCOL" in content.upper()

    def test_has_security_constraints(self) -> None:
        """The prompt has a Security/Sandbox section."""
        content = _read("SYSTEMPROMPT.md")
        assert "SANDBOX" in content.upper() or "SECURITY" in content.upper()

    def test_has_examples(self) -> None:
        """The prompt has at least one worked example."""
        content = _read("SYSTEMPROMPT.md")
        assert "EXAMPLE" in content.upper()

    def test_no_hermes_attribution(self) -> None:
        """The prompt must NOT mention 'Hermes' as an attribution (research only)."""
        content = _read("SYSTEMPROMPT.md")
        # The only acceptable mention is "research references only" or similar.
        # A bare "Built on Hermes" or "Based on Hermes" is forbidden.
        lower = content.lower()
        assert "based on hermes" not in lower
        assert "built on hermes" not in lower
        assert "powered by hermes" not in lower

    def test_has_version_history(self) -> None:
        """The prompt has a version history section."""
        content = _read("SYSTEMPROMPT.md")
        assert "VERSION" in content.upper() and "3.0.0" in content

    def test_mentions_ai_assistance(self) -> None:
        """The prompt acknowledges AI-assisted development."""
        content = _read("SYSTEMPROMPT.md")
        assert "AI" in content.upper() or "artificial intelligence" in content.lower()


class TestLicenseExtended:
    """Tests for the extended MIT LICENSE."""

    def test_file_exists(self) -> None:
        """LICENSE must exist."""
        assert (REPO_ROOT / "LICENSE").exists()

    def test_has_standard_mit_core(self) -> None:
        """The LICENSE has the standard MIT permission grant."""
        content = _read("LICENSE")
        assert "Permission is hereby granted, free of charge" in content
        # Normalize whitespace for the multi-line phrase.
        normalized = " ".join(content.split())
        assert "all copies or substantial portions of the Software" in normalized

    def test_has_no_warranty_clause(self) -> None:
        """The LICENSE has the standard 'AS IS' warranty disclaimer."""
        content = _read("LICENSE")
        assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in content
        assert "WITHOUT WARRANTY OF ANY KIND" in content

    def test_mentions_creator(self) -> None:
        """The LICENSE mentions the creator's name."""
        content = _read("LICENSE")
        assert "Dearly Febriano Irwansyah" in content

    def test_mentions_indonesia(self) -> None:
        """The LICENSE mentions Indonesia."""
        content = _read("LICENSE")
        assert "Indonesia" in content or "Indonesian" in content

    def test_has_extended_terms_section(self) -> None:
        """The LICENSE has an EXTENDED TERMS section."""
        content = _read("LICENSE")
        assert "EXTENDED TERMS" in content.upper()

    def test_has_attribution_requirement(self) -> None:
        """The LICENSE has an attribution requirement clause."""
        content = _read("LICENSE")
        assert "ATTRIBUTION" in content.upper()

    def test_has_trademark_notice(self) -> None:
        """The LICENSE has a trademark notice."""
        content = _read("LICENSE")
        assert "TRADEMARK" in content.upper()

    def test_has_patent_disclaimer(self) -> None:
        """The LICENSE has a patent disclaimer."""
        content = _read("LICENSE")
        assert "PATENT" in content.upper()

    def test_has_contribution_license(self) -> None:
        """The LICENSE has a contribution license clause."""
        content = _read("LICENSE")
        assert "CONTRIBUTION" in content.upper() or "pull request" in content.lower()

    def test_has_ai_acknowledgment(self) -> None:
        """The LICENSE acknowledges AI-assisted development."""
        content = _read("LICENSE")
        assert "AI-ASSISTED" in content.upper() or "AI-powered" in content.lower()

    def test_has_indonesian_copyright_law(self) -> None:
        """The LICENSE acknowledges Indonesian copyright law."""
        content = _read("LICENSE")
        assert "UU No. 28" in content or "Hak Cipta" in content or "moral rights" in content.lower()

    def test_has_security_disclosure_clause(self) -> None:
        """The LICENSE has a security disclosure clause."""
        content = _read("LICENSE")
        assert "SECURITY" in content.upper() and "vulnerability" in content.lower()

    def test_has_high_risk_disclaimer(self) -> None:
        """The LICENSE disclaims fitness for high-risk applications."""
        content = _read("LICENSE")
        assert "HIGH-RISK" in content.upper() or "high-risk" in content.lower()

    def test_version_in_license(self) -> None:
        """The LICENSE version (3.0.0) is mentioned."""
        content = _read("LICENSE")
        assert "3.0.0" in content
