## OpenForge Security Policy

### Supported Versions

| Version   | Supported          |
|-----------|--------------------|
| v5.x.x    | :white_check_mark: |
| v4.x.x    | :warning: security fixes if still exploited broadly |
| < v4.0    | :x: unsupported    |

### Reporting a Vulnerability

**Please do NOT file a public GitHub issue for security vulnerabilities.**

Instead, report privately:

- GitHub Security Advisories: `https://github.com/neuralforgeio/openforge/security/advisories/new`
- Email: include `SECURITY` in the subject to reach the maintainer directly.

Expected response: acknowledgement within 72 hours; triage and disclosure timeline agreed with the reporter.

### Common Categories We Care About

- Credential exposure (`.env`, `~/.openforge/secrets/` read/write outside owner)
- Tool sandbox bypass (terminal reading `~/.openforge/` or executing outside the sandbox)
- Token smuggling in errors / logs / traces sent to external providers
- Malicious skill / tool code execution without user consent
- Unsafe update path (downgrade to unsigned code, FORCE attacks)

### Out of Scope

- Performance improvements, flaky tests, UI polish
- Missing `openforge doctor`/formatting bugs that don't affect safety
- Typos in docs (open a normal issue instead)

Thank you for keeping OpenForge safe. 🔒
