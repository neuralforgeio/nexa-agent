"""S-08: Plugin manifest parser + validator (TOML)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str = ""
    entry: str = ""                     # python entry point (module:function)
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


def parse_manifest(path: str) -> PluginManifest:
    """Load a ``forge-plugin.toml`` and validate its required fields."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    m = data.get("plugin")
    if not isinstance(m, dict):
        raise ValueError("missing [plugin] section")
    for field_name in ("name", "version", "description", "entry"):
        if not m.get(field_name):
            raise ValueError(f"manifest missing required field: {field_name}")
    return PluginManifest(
        name=m["name"],
        version=m["version"],
        description=m["description"],
        author=m.get("author", ""),
        entry=m["entry"],
        permissions=list(m.get("permissions", [])),
        dependencies=list(m.get("dependencies", [])),
    )
