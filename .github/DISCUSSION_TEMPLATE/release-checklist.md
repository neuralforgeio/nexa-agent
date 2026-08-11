# Pre-release checklist (for maintainers)
1. Version agreement across pyproject.toml, package.json, openforge_web/package.json, config.yaml.
2. `pytest tests/ --ignore=tests/test_llamacpp_real.py` → green (paste tail).
3. Smoke: `openforge --version` · `openforge doctor` · `openforge-gateway --help`.
4. Triad (3/3) for every claim you intend to ship.
5. Tag annotated → `gh release create` → verify parity via the remote API.
