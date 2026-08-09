# Research: Continuous Testing for OpenForge

## Summary
How the OpenForge should test itself periodically, and what levels of
confidence we expect per phase.

## Findings

### Existing test pyramid
- **Unit tests** (`tests/*.py`): 649+ passing.
- **Smoke tests**: boot + health endpoints.
- **Integration tests**: `tests/test_llamacpp_real.py` — real HTTP calls
  to a local llama.cpp server (requires `FORGE_E2E_LLAMACPP=1`).
- **E2E tests**: web-UI paths exercised by manual testing.

### Layers the QA loop currently covers
- Layer 0: `pytest -q tests/`
- Layer 1: `tsc --noEmit` (frontend types)
- Layer 2: `next build` (production build)
- Layer 3: `eslint .` (lint)
- Layer 4 (manual, gated by env vars): llama.cpp E2E pushed into
  `Documents/testing-result/<UTC-timestamp>/`.

### Auxiliary tools
- **pytest-xdist**: parallel test execution (`pytest -n auto`).
- **pytest-timeout**: hard wall-clock ceiling per test (prevents a
  network hook from hanging the suite forever).

## Benchmark Comparison

| Suite type | Tool | Coverage | Acts against | Default |
|------------|------|----------|--------------|---------|
| Unit | pytest | High | Python modules | Yes |
| Integration | pytest | Medium | Tools + providers | Yes |
| E2E | playwright/manual | Low (skipped) | Web UI+llama.cpp | Limited |

## Recommendations

1. Persist test-results directory forever under
   `Documents/testing-result/` so a developer can inspect later. Our
   `tests/test_llamacpp_real.py` already does that.
2. Keep `FORGE_E2E_LLAMACPP=1` as the default-off gate: without it, the
   local model tests are skipped cleanly. CI machines never need to spin
   llama.cpp.
3. Extend `pytest.ini_options.markers` rather than ad-hoc skip comments.

## Open Questions
- Are we going to build our own assertion harness around OpenRouter,
  or keep validating via public endpoints (which is cheap/free for
  identity checks)?
- How do we make parallization between sibling tests safe — lock SQLite,
  shard by DB path, or use in-memory SQLite per test?