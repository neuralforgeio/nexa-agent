## CONTRIBUTING to OpenForge

We welcome PRs! OpenForge evolved from nexa-agent into a stable, local-first AI agent. To keep quality high, follow these rules.

### Setup

```bash
git clone https://github.com/neuralforgeio/openforge.git
cd openforge
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # or source .venv/bin/activate
pip install -e ".[dev]"
```

### Dev loop

```bash
pytest tests/ -q --ignore=tests/integration   # backend
npm run build && npx vitest run               # frontend
npx eslint .                                  # lint
```

### Commit style

Use [Conventional Commits](https://www.conventionalcommits.org):

- `feat:` user-visible feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` no behavior change
- `chore:` dependency/config/maintenance

Include a body describing what/why/risk; for releases include the version.

### Pull requests

- Fill `.github/PULL_REQUEST_TEMPLATE.md` fully.
- Follow SemVer. Do not open a PR that changes `version` (loc: pyproject.toml / config.yaml / package.json) — that is done by maintainers during the release ceremony.
- Tests MUST pass. "Ready for review" means CI is green.
- No secrets in the diff. Ever.

### Branch model

We develop directly on `main` with release tags. There are no `next`/`development` branches. Cut a feature PR straight onto `main`.

Thank you! 🙏
