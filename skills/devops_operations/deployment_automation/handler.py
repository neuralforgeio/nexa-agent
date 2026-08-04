"""
Skill: deployment_automation
============================

Intended purpose (per manifest): deploy an application directory to a chosen
hosting target (aws | gcp | azure | vercel | netlify | heroku) with a deploy
config, returning the deployment URL, the captured deploy logs, and the
rollback command.

This handler is HONEST BY DESIGN: it performs NO deployment whatsoever. The
agent runtime has no cloud credentials, deploy CLIs, or network authorisation
for any of the supported targets, so there is nothing truthful this skill
could do besides:

  1. Validate the input and confirm ``app_path`` really exists inside the
     workspace (via :func:`agent.tool_api.workspace_path`, i.e. sandboxed).
  2. Return a schema-valid result whose fields state, in plain language,
     that no deploy was attempted and which command a human would run (or
     authorise) next: ``deployment_url`` is empty, ``logs`` says credentials
     were not provided and nothing was attempted, and ``rollback_command`` is
     empty because there is nothing deployed to roll back.

Permissions used:
  * ``terminal:execute`` / ``network:*`` — declared by the manifest; this
    handler executes no terminal commands and makes no network calls.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agent import tool_api
from skills._common import require
from skills.registry import SkillInputError

__all__ = ["handle"]

_TARGETS = ("aws", "gcp", "azure", "vercel", "netlify", "heroku")

# Per-target commands a human WITH credentials would run — surfaced verbatim
# in the logs field so the result is actionable without pretending anything ran.
_HUMAN_NEXT_STEP = {
    "aws": "aws deploy push --application-name <app> (after `aws configure`)",
    "gcp": "gcloud app deploy (after `gcloud auth login`)",
    "azure": "az webapp up (after `az login`)",
    "vercel": "vercel --prod (after `vercel login`)",
    "netlify": "netlify deploy --prod (after `netlify login`)",
    "heroku": "git push heroku main (after `heroku login`)",
}


def _confirm_app_path(app_path: str) -> Path:
    """Resolve ``app_path`` inside the workspace and require it to exist."""
    try:
        p = tool_api.workspace_path(app_path)
    except ValueError as exc:
        raise SkillInputError(f"invalid app_path {app_path!r}: {exc}") from exc
    if not p.exists():
        raise SkillInputError(
            f"app_path {app_path!r} does not exist in the workspace "
            f"(resolved to {Path(p)})"
        )
    return p


async def handle(input_data: dict, provider) -> dict:
    """
    Confirm the app path exists, then return a truthful no-deploy result.

    ``provider`` is accepted for signature compatibility but unused — this
    skill calls no LLM and no cloud API.
    """
    app_path = require(input_data, "app_path", str, "application directory")
    target = require(input_data, "target", str, "hosting target")
    config = require(input_data, "config", dict, "deploy config")
    if target not in _TARGETS:
        raise SkillInputError(
            f"target must be one of {sorted(_TARGETS)}, got {target!r}"
        )

    resolved = _confirm_app_path(app_path)

    logs = (
        "deployment requires cloud credentials not provided "
        "(no actual deploy was attempted). "
        f"Target {target!r} with config keys {sorted(config.keys()) or '[]'} "
        f"against workspace path {Path(resolved)} (exists). "
        f"A human with credentials could run: {_HUMAN_NEXT_STEP[target]}."
    )

    return {
        "deployment_url": "",
        "logs": logs,
        # Nothing was deployed, so there is nothing to roll back.
        "rollback_command": "",
    }
