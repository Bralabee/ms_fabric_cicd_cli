## Description

<!-- Provide a concise summary of the changes and the motivation behind them. -->

## Type of Change

<!-- Check all that apply -->
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Refactor (code change that neither fixes a bug nor adds a feature)
- [ ] Documentation update
- [ ] CI/CD or infrastructure change
- [ ] Configuration/template change

## Related Issues

<!-- Link any related issues: Fixes #123, Closes #456 -->

## Testing

- [ ] Unit tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Formatting verified (`black --check .`)
- [ ] Type checks pass (`mypy src/`)
- [ ] Blueprint validation passes (if templates changed)
- [ ] Integration tests pass (if applicable, `make test-integration`)

## Security Checklist

- [ ] No secrets, tokens, or credentials in code or config
- [ ] No hardcoded organization names or URLs
- [ ] `.env.template` updated if new env vars added
- [ ] `detect-secrets` baseline updated if needed

## Deployment Impact

- [ ] No deployment impact
- [ ] Requires environment variable changes (document below)
- [ ] Requires Fabric capacity changes
- [ ] Breaking change to YAML config schema (document migration path)
- [ ] Consumer repos (e.g., `fabric_cicd_test_repo`) need updates

## Screenshots / Logs

<!-- If applicable, add screenshots or relevant log output -->

## Reviewer Notes

<!-- Any specific areas you'd like reviewers to focus on -->
