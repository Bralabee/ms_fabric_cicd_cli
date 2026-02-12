# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 1.7.x   | :white_check_mark: |
| < 1.7   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** create a public GitHub issue
2. Email the maintainers directly or use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
3. Include a description of the vulnerability, steps to reproduce, and potential impact
4. Allow reasonable time for a fix before public disclosure

## Security Practices

### Secrets Management
- **Waterfall credential resolution**: Environment Variables → `.env` → Azure Key Vault
- `.env` files are `.gitignore`-d and never committed
- All tokens/secrets are obfuscated in logs and audit trails
- `detect-secrets` pre-commit hook prevents accidental credential commits

### CI/CD Security
- **Bandit** static analysis scans for Python security anti-patterns
- **Dependabot** monitors dependencies for known vulnerabilities (weekly)
- **Pre-commit hooks** enforce security checks before every commit
- GitHub Actions secrets are scoped to deployment environments

### Audit Trail
- All Fabric operations are logged to `audit_logs/*.jsonl`
- Audit logs never contain secrets or tokens
- JSONL format enables tamper-evident log analysis

### Docker Security
- Production images run as non-root user
- Minimal base images (python:3.11-slim)
- No secrets baked into Docker images — injected via environment variables at runtime
