# Contributing to USF Fabric CLI CI/CD

Thank you for your interest in contributing! This document provides guidelines for contributing to the active USF Fabric CLI CI/CD project.

## Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/usf_fabric_cli_cicd.git
cd usf_fabric_cli_cicd

# 2. Set up environment
conda env create -f environment.yml
conda activate fabric-cli-cicd

# 3. Install in editable mode
pip install -e .

# 4. Install pre-commit hooks
pre-commit install

# 5. Verify setup
make test
```

## Development Workflow

### Branch Naming Convention

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<description>` | `feature/add-kql-support` |
| Bug fix | `fix/<issue>-<description>` | `fix/42-capacity-timeout` |
| Hotfix | `hotfix/<version>-<description>` | `hotfix/1.7.6-auth-fix` |
| Docs | `docs/<description>` | `docs/update-blueprint-catalog` |

### Workflow

1. Sync with upstream: `git pull origin main`
2. Create feature branch: `git checkout -b feature/your-feature`
3. Make changes following coding standards below
4. Run quality checks: `make ci` (runs lint + typecheck + test + security)
5. Commit with conventional messages (see below)
6. Push and create PR

### Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Reflex item type support
fix: resolve capacity timeout on F2
docs: update blueprint catalog with new templates
refactor: extract git connection retry logic
test: add integration tests for GitHub provider
ci: upgrade codecov action to v4
chore: update dependencies
```

## Coding Standards

- **Formatter**: `black` (line-length: 88)
- **Linter**: `flake8` (line-length: 88)
- **Import Sorting**: `isort` (profile: black)
- **Type Checker**: `mypy`
- **Security Scanner**: `bandit`
- **All new functions** must include type hints and docstrings
- **Use `logging`** module, never `print()`
- **Use custom exceptions** from `src/usf_fabric_cli/exceptions.py`

### Docstring Format (Google-style)

```python
def deploy_workspace(
    config_path: str,
    environment: str = "dev",
    dry_run: bool = False,
) -> dict:
    """Deploy a Fabric workspace from YAML configuration.

    Args:
        config_path: Path to the YAML configuration file.
        environment: Target environment (dev/test/prod).
        dry_run: If True, validate without deploying.

    Returns:
        Dictionary containing deployment results and audit metadata.

    Raises:
        FabricCLIError: If the Fabric CLI command fails.
        FileNotFoundError: If the config file doesn't exist.
    """
```

## Testing

```bash
make test              # Unit tests (no credentials needed)
make test-integration  # Integration tests (needs .env credentials)
make lint              # Linting only
make ci                # Full CI gate (lint + typecheck + test + security)
```

- All PRs must pass unit tests
- New features require accompanying tests
- Minimum 70% coverage on changed files
- Blueprint templates must be validated: `make validate`

## Security Rules

- **NEVER** commit secrets, tokens, or credentials
- **NEVER** hardcode organization-specific values
- Update `.env.template` when adding new environment variables
- Run `detect-secrets scan` if modifying files that may contain secrets
- All env-specific values must use `${VAR_NAME}` substitution

## Consumer Repo Updates

If your changes affect the CLI interface (new flags, changed behavior):
1. Update `fabric_cicd_test_repo` workflows to match
2. Test with a real feature workspace create/cleanup cycle
3. Document migration steps for existing consumer repos

## Pull Request Checklist

- [ ] Tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] No secrets in code
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated for user-facing changes
- [ ] PR description fills out the template
- [ ] Blueprint templates validated (`make validate`)
