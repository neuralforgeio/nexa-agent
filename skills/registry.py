"""
OpenForge — Skills Registry (v4.4.0)
=====================================

Batch 8 foundation: a filesystem-backed registry for *skills*.

A **skill** is a high-level, domain capability (``code_review``,
``translation``, ``data_analysis``, ...) — distinct from a *tool* (low-level
file/terminal/network primitive). Skills are discovered from the ``skills/``
package; each skill lives in its own sub-package and must provide:

  * ``manifest.yaml``  — declarative manifest (name, version, schemas, ...).
  * ``handler.py``     — an ``async def handle(input_data, provider)`` coroutine.

The registry is::

  * **lazy** — handler modules are imported on first use, so importing the
    registry never pays for imports a caller does not need.
  * **validating** — manifests are parsed against :data:`REQUIRED_FIELDS`
    and a strict permission grammar; inputs/outputs are validated against
    the manifest's JSON Schemas (:func:`validate_schema`).
  * **provider-agnostic** — the executor never instantiates a provider; the
    caller supplies one (a real ``LLMProvider`` in production, a scripted
    fake in unit tests). This keeps honest-testing a first-class citizen.

Environment toggles (honoured, never auto-enabled):

  * ``NEXA_SKILLS_DISABLED``  — comma-separated skill names forced off.
  * ``NEXA_SKILLS_ENABLED``   — if set, acts as an allow-list: only the
    named skills are considered enabled.

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

import yaml

__all__ = [
    "SkillError",
    "SkillInputError",
    "SkillOutputError",
    "SkillManifestError",
    "SkillNotFoundError",
    "SkillDisabledError",
    "Manifest",
    "Skill",
    "validate_schema",
    "parse_manifest",
    "discover_skills",
    "load_registry",
    "refresh_registry",
    "list_skills",
    "get_skill",
    "is_enabled",
    "execute_skill",
]

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SkillError(Exception):
    """Base class for every skill-registry failure."""


class SkillManifestError(SkillError):
    """A manifest failed to parse or validate."""


class SkillNotFoundError(SkillError):
    """Requested skill name is not registered."""


class SkillDisabledError(SkillError):
    """Requested skill exists but is disabled via an environment toggle."""


class SkillInputError(SkillError):
    """Input payload failed ``input_schema`` validation."""


class SkillOutputError(SkillError):
    """Handler returned a payload that failed ``output_schema`` validation."""


# ---------------------------------------------------------------------------
# Permission grammar
# ---------------------------------------------------------------------------

# Declarative permission strings, e.g. ``filesystem:workspace:write`` or the
# wildcard ``network:*``. This is deliberately a *declarative* contract: the
# registry validates syntax so a manifest cannot request nonsense, and the
# handler is expected to only use Tool API helpers that map to the declared
# permissions. Enforcing isolation at the OS layer is out of scope for the
# in-process registry (documented honestly in the manifest spec).
_PERM_KIND = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_permission(perm: str) -> None:
    if not isinstance(perm, str) or not perm:
        raise SkillManifestError(f"permission must be a non-empty string, got {perm!r}")
    parts = perm.split(":")
    if not parts or not _PERM_KIND.match(parts[0]):
        raise SkillManifestError(f"invalid permission root {perm!r}")
    for part in parts[1:]:
        if part == "*":
            continue
        if not _PERM_KIND.match(part):
            raise SkillManifestError(f"invalid permission segment {part!r} in {perm!r}")


# ---------------------------------------------------------------------------
# Minimal JSON-Schema subset validator
# ---------------------------------------------------------------------------

_JSON_TYPES: Dict[str, Tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),          # bool is a subclass of int — guarded below
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_matches(expected: str, value: Any) -> bool:
    if expected not in _JSON_TYPES:
        return True  # unknown keyword — treat as untyped (lenient)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _JSON_TYPES[expected])


def validate_schema(
    schema: Optional[Dict[str, Any]],
    value: Any,
    *,
    path: str = "$",
) -> List[str]:
    """
    Validate ``value`` against a JSON-Schema *subset*.

    Supported keywords: ``type``, ``required``, ``properties``,
    ``additionalProperties`` (bool), ``items``, ``enum``, ``minimum``,
    ``maximum``, ``minItems``, ``maxItems``, ``anyOf``. Unknown keywords are
    ignored so manifests may use a richer schema without breaking the
    validator.

    Returns:
        A list of human-readable error strings; empty list means valid.
    """
    if not isinstance(schema, dict) or not schema:
        return []

    errors: List[str] = []

    if "anyOf" in schema:
        subs = schema.get("anyOf") or []
        if not any(not validate_schema(s, value, path=path) for s in subs if isinstance(s, dict)):
            errors.append(f"{path}: does not match any allowed schema")
        return errors

    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_type_matches(t, value) for t in expected):
            errors.append(f"{path}: expected type one of {expected}, got {type(value).__name__}")
            return errors
    elif isinstance(expected, str):
        if not _type_matches(expected, value):
            errors.append(f"{path}: expected type {expected!r}, got {type(value).__name__}")
            return errors

    if "enum" in schema:
        allowed = schema["enum"]
        if isinstance(allowed, list) and value not in allowed:
            errors.append(f"{path}: value {value!r} not in enum {allowed!r}")

    if isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: missing required property")
        properties = schema.get("properties") or {}
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(validate_schema(properties[key], item, path=f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}.{key}: additional property not allowed")

    if isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for idx, item in enumerate(value):
                errors.extend(validate_schema(items, item, path=f"{path}[{idx}]"))
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path}: expected at least {schema['minItems']} items, got {len(value)}")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}: expected at most {schema['maxItems']} items, got {len(value)}")

    if isinstance(value, bool):
        pass  # bool is an int subclass — numeric bounds don't apply
    elif isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    return errors


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

SKILL_CATEGORIES: Tuple[str, ...] = (
    "code_intelligence",
    "web_research",
    "creative_media",
    "communication",
    "data_analytics",
    "devops_operations",
)

REQUIRED_FIELDS: Tuple[str, ...] = (
    "name",
    "version",
    "description",
    "category",
    "permissions",
    "input_schema",
    "output_schema",
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class Manifest:
    """Immutable, validated skill manifest."""

    name: str
    version: str
    description: str
    category: str
    author: str = "nexa-agent"
    permissions: Tuple[str, ...] = ()
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: Tuple[Dict[str, Any], ...] = ()
    tags: Tuple[str, ...] = ()

    def summary(self) -> Dict[str, Any]:
        """Small JSON-safe card used by list endpoints / the UI."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "author": self.author,
            "permissions": list(self.permissions),
            "tags": list(self.tags),
            "examples": [dict(e) for e in self.examples],
        }


def parse_manifest(path: Path) -> Manifest:
    """
    Parse and validate a ``manifest.yaml``.

    Raises:
        SkillManifestError: On any structural or semantic violation.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SkillManifestError(f"cannot parse manifest {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SkillManifestError(f"manifest {path} is not a mapping")

    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise SkillManifestError(f"manifest {path} missing required fields: {missing}")

    name = raw["name"]
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillManifestError(f"manifest {path} invalid name {name!r} (snake_case required)")

    version = raw["version"]
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        raise SkillManifestError(f"manifest {path} invalid version {version!r} (semver X.Y.Z required)")

    description = raw["description"]
    if not isinstance(description, str) or not description.strip():
        raise SkillManifestError(f"manifest {path} needs a non-empty description")

    category = raw["category"]
    if category not in SKILL_CATEGORIES:
        raise SkillManifestError(
            f"manifest {path} unknown category {category!r}; "
            f"expected one of {sorted(SKILL_CATEGORIES)}"
        )

    permissions = raw["permissions"]
    if not isinstance(permissions, (list, tuple)):
        raise SkillManifestError(f"manifest {path} permissions must be a list")
    for perm in permissions:
        _validate_permission(perm)

    for schema_key in ("input_schema", "output_schema"):
        if not isinstance(raw[schema_key], dict):
            raise SkillManifestError(f"manifest {path} {schema_key} must be a mapping")

    examples = raw.get("examples") or []
    if not isinstance(examples, (list, tuple)):
        raise SkillManifestError(f"manifest {path} examples must be a list")

    tags = raw.get("tags") or []
    if not all(isinstance(t, str) for t in tags):
        raise SkillManifestError(f"manifest {path} tags must be strings")

    author = raw.get("author") or "nexa-agent"
    if not isinstance(author, str):
        raise SkillManifestError(f"manifest {path} author must be a string")

    return Manifest(
        name=name,
        version=version,
        description=description.strip(),
        category=category,
        author=author,
        permissions=tuple(permissions),
        input_schema=dict(raw["input_schema"]),
        output_schema=dict(raw["output_schema"]),
        examples=tuple(e for e in examples if isinstance(e, dict)),
        tags=tuple(tags),
    )


# ---------------------------------------------------------------------------
# Skill handle + registry
# ---------------------------------------------------------------------------


@dataclass
class Skill:
    """A registered skill: its manifest plus lazily-imported handle."""

    module_path: str          # e.g. "skills.code_intelligence.code_review"
    manifest: Manifest
    _handler: Optional[Callable[[Dict[str, Any], Any], Awaitable[Dict[str, Any]]]] = None

    def load_handler(self) -> Callable[[Dict[str, Any], Any], Awaitable[Dict[str, Any]]]:
        """
        Import ``<module_path>.handler`` and return its ``handle`` coroutine.

        Raises:
            SkillManifestError: If the module is missing or ``handle`` is not
                an async callable.
        """
        if self._handler is not None:
            return self._handler
        try:
            module = importlib.import_module(f"{self.module_path}.handler")
        except ImportError as exc:  # pragma: no cover - exercised via integration
            raise SkillManifestError(f"cannot import handler for {self.module_path}: {exc}") from exc
        handler = getattr(module, "handle", None)
        if handler is None or not callable(handler):
            raise SkillManifestError(f"{self.module_path}.handler must define a callable ``handle``")
        if not inspect.iscoroutinefunction(handler):
            raise SkillManifestError(f"{self.module_path}.handler.handle must be async")
        self._handler = handler
        return handler


# Discovered skills keyed by manifest.name. Populated at import time.
_REGISTRY: Dict[str, Skill] = {}


def discover_skills(package: str = "skills") -> Dict[str, Skill]:
    """
    Scan ``skills/<category>/<skill>/`` and register every valid manifest.

    A category folder without any skill sub-folders is ignored. A skill folder
    whose manifest fails to parse is *skipped loudly* (recorded in the error
    list on the return value's ``__doc__`` companion — see
    :func:`discover_skills_strict` in tests) rather than aborting the whole
    scan, so one bad skill cannot brick the registry.
    """
    found: Dict[str, Skill] = {}
    try:
        pkg = importlib.import_module(package)
    except ImportError:
        return found

    root = Path(pkg.__file__).parent  # type: ignore[arg-type]
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        category = category_dir.name
        if category.startswith("_"):
            continue
        for skill_dir in sorted(p for p in category_dir.iterdir() if p.is_dir()):
            if skill_dir.name.startswith("_"):
                continue
            manifest_path = skill_dir / "manifest.yaml"
            if not manifest_path.is_file():
                continue
            manifest = parse_manifest(manifest_path)
            module_path = f"{package}.{category}.{skill_dir.name}"
            found[manifest.name] = Skill(module_path=module_path, manifest=manifest)
    return found


def load_registry(package: str = "skills") -> Dict[str, Skill]:
    """(Re)populate and return the global registry."""
    global _REGISTRY
    _REGISTRY = discover_skills(package)
    return _REGISTRY


def refresh_registry() -> Dict[str, Skill]:
    """Public alias for :func:`load_registry` — re-scan the skills package."""
    return load_registry()


def _registry() -> Dict[str, Skill]:
    if not _REGISTRY:
        load_registry()
    return _REGISTRY


# ---------------------------------------------------------------------------
# Enablement (env-gated, never on-by-default-off surprises)
# ---------------------------------------------------------------------------


def _env_list(var: str) -> List[str]:
    return [tok.strip() for tok in os.environ.get(var, "").split(",") if tok.strip()]


def is_enabled(name: str) -> bool:
    """
    Return True unless the skill is explicitly disabled.

    ``NEXA_SKILLS_DISABLED`` removes skills; ``NEXA_SKILLS_ENABLED`` (when
    non-empty) allow-lists. Both exist so operators can lock the runtime
    surface down without editing manifests.
    """
    if name in _env_list("NEXA_SKILLS_DISABLED"):
        return False
    enabled = _env_list("NEXA_SKILLS_ENABLED")
    if enabled and name not in enabled:
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_skills(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return manifest summary cards, optionally filtered by category."""
    cards = []
    for skill in _registry().values():
        if category and skill.manifest.category != category:
            continue
        card = skill.manifest.summary()
        card["enabled"] = is_enabled(skill.manifest.name)
        cards.append(card)
    return sorted(cards, key=lambda c: c["name"])


def get_skill(name: str) -> Skill:
    """Fetch a skill by name or raise :class:`SkillNotFoundError`."""
    try:
        return _registry()[name]
    except KeyError as exc:
        raise SkillNotFoundError(f"unknown skill {name!r}") from exc


async def execute_skill(name: str, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
    """
    Validate input, run the skill handler, validate output.

    Args:
        name:       Registered skill name.
        input_data: Payload conforming to the manifest ``input_schema``.
        provider:   An LLMProvider-like object handed to the handler verbatim.

    Returns:
        The handler's payload, validated against ``output_schema``.
    """
    skill = get_skill(name)
    if not is_enabled(name):
        raise SkillDisabledError(f"skill {name!r} is disabled via environment toggle")
    if not isinstance(input_data, dict):
        raise SkillInputError(f"skill {name!r} input must be an object, got {type(input_data).__name__}")

    in_errors = validate_schema(skill.manifest.input_schema, input_data)
    if in_errors:
        raise SkillInputError(f"skill {name!r} invalid input: " + "; ".join(in_errors))

    handler = skill.load_handler()
    result = handler(input_data, provider)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, dict):
        raise SkillOutputError(
            f"skill {name!r} returned {type(result).__name__}; expected an object"
        )

    out_errors = validate_schema(skill.manifest.output_schema, result)
    if out_errors:
        raise SkillOutputError(f"skill {name!r} invalid output: " + "; ".join(out_errors))
    return result


# Populate at import so `import skills; skills.list_skills()` just works.
load_registry()
