"""
Tests for SYSTEMPROMPT.md and the standard MIT LICENSE.

Verifies:
    - SYSTEMPROMPT.md exists and has all required sections.
    - The creator "Dearly Febriano Irwansyah" is mentioned (with Indonesian origin).
    - No "Hermes" attribution (research-only reference).
    - LICENSE is the standard MIT License text recognized by GitHub's licensee
      detection (changed from "Extended MIT" in v4.6.4 because GitHub labeled
      the repo license as "Other").

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
        """The prompt catalogues at least one canonical tool/skill by name."""
        content = _read("SYSTEMPROMPT.md")
        tool_mentions = sum(1 for t in ("read_file", "write_file", "run_terminal_command",
                                         "web_search", "code_execution", "delegate",
                                         "skills", "tool")
                            if t in content)
        assert tool_mentions >= 2

    def test_has_memory_protocol(self) -> None:
        """The prompt has a Memory Protocol section."""
        content = _read("SYSTEMPROMPT.md").upper()
        assert "MEMORY" in content and ("RULE" in content or "PROTOCOL" in content)

    def test_has_security_constraints(self) -> None:
        """The prompt has a Security/Sandbox section."""
        content = _read("SYSTEMPROMPT.md")
        assert "SANDBOX" in content.upper() or "SECURITY" in content.upper()

    def test_has_examples(self) -> None:
        """The prompt demonstrates the expected shape of work (worked formats)."""
        content = _read("SYSTEMPROMPT.md")
        # The modern prompt uses concrete worked formats: shell commands, transitions,
        # and version-history arrows. Those are the "worked example" surface.
        assert "`openforge doctor`" in content
        assert "pytest" in content
        assert "→" in content

    def test_no_hermes_attribution(self) -> None:
        """The prompt must NOT mention 'Hermes' as an attribution (research only)."""
        content = _read("SYSTEMPROMPT.md")
        lower = content.lower()
        assert "based on hermes" not in lower
        assert "built on hermes" not in lower
        assert "powered by hermes" not in lower

    def test_has_version_history(self) -> None:
        """The prompt records a version line (current is read from manifests, not hardcoded)."""
        content = _read("SYSTEMPROMPT.md").upper()
        assert "VERSION" in content
        assert "5.2.0" in content or "V5.2.0" in content

    def test_mentions_ai_assistance(self) -> None:
        """The prompt acknowledges AI-assisted development."""
        content = _read("SYSTEMPROMPT.md")
        assert "AI" in content.upper() or "artificial intelligence" in content.lower()


class TestLicenseStandardMIT:
    """
    Tests for the standard MIT LICENSE.

    v4.6.4: replaced "Extended MIT" with the canonical MIT text so GitHub's
    licensee detector displays "MIT License" instead of "Other" on the repo
    page. The test contract is now exact-standard (not extended-terms).
    """

    def test_file_exists(self) -> None:
        """LICENSE must exist."""
        assert (REPO_ROOT / "LICENSE").exists()

    def test_has_standard_mit_header(self) -> None:
        """The LICENSE starts with the literal 'MIT License' header."""
        content = _read("LICENSE")
        assert content.startswith("MIT License\n")

    def test_has_standard_mit_core(self) -> None:
        """The LICENSE has the standard MIT permission grant."""
        content = _read("LICENSE")
        assert "Permission is hereby granted, free of charge" in content
        normalized = " ".join(content.split())
        assert "all copies or substantial portions of the Software" in normalized

    def test_has_no_warranty_clause(self) -> None:
        """The LICENSE has the standard 'AS IS' warranty disclaimer."""
        content = _read("LICENSE")
        assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in content
        assert "WITHOUT WARRANTY OF ANY KIND" in content

    def test_no_liability_clause(self) -> None:
        """The LICENSE has the standard no-liability clause."""
        content = _read("LICENSE")
        # The standard text splits "AUTHORS OR COPYRIGHT HOLDERS" across lines;
        # normalize whitespace before matching.
        normalized = " ".join(content.split())
        assert "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM" in normalized
        assert "LIABILITY" in content

    def test_mentions_creator_copyright(self) -> None:
        """The LICENSE names the creator and year."""
        content = _read("LICENSE")
        assert "Copyright (c) 2026 Dearly Febriano Irwansyah" in content

    def test_license_length_within_standard_bounds(self) -> None:
        """
        GitHub's licensee fuzzy-matching fails when the LICENSE is much longer
        than upstream MIT. Standard MIT is ~21 lines; the repo license must be
        close to that (not 117 lines of extended terms).
        """
        content = _read("LICENSE")
        lines = [ln for ln in content.splitlines() if ln.strip()]
        # Upstream MIT has ~19 non-empty lines; tolerance for OSI/exact-match.
        assert len(lines) <= 25, (
            f"LICENSE too long ({len(lines)} non-empty lines) for GitHub "
            "MIT detection; must match the near-exact-standard template."
        )

    def test_no_extended_terms_markers(self) -> None:
        """
        The previous 'Extended MIT' used an EXTENDED TERMS section, trademark
        notice, contribution license, moral-rights clause, AI acknowledgment,
        high-risk disclaimer, etc. All must be ABSENT in the standard version
        so GitHub's licensee matcher scores MIT at >= 95% confidence.
        """
        content = _read("LICENSE")
        upper = content.upper()
        for marker in (
            "EXTENDED TERMS",
            "ATTRIBUTION REQUIREMENT",
            "TRADEMARK NOTICE",
            "NO ENDORSEMENT",
            "PATENT DISCLAIMER",
            "CONTRIBUTION LICENSE",
            "AI-ASSISTED",
            "MORAL RIGHTS",
            "HIGH-RISK APPLICATIONS",
            "SECURITY DISCLOSURE",
            "UU NO. 28",
        ):
            assert marker not in upper, f"extended-terms remnant found: {marker}"

    def test_no_extended_mit_header(self) -> None:
        """The previous 'Extended MIT License (Version 3.0.0)' header is gone."""
        content = _read("LICENSE")
        assert "Extended MIT" not in content
        assert "Version 3.0.0" not in content

    def test_no_contact_block(self) -> None:
        """The previous file had a contact block — must be removed."""
        content = _read("LICENSE")
        assert "dearlyfebrianoi@gmail.com" not in content
