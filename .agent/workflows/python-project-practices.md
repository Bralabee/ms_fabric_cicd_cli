---
description: Guidelines for working on Python projects with conda environments
---

# Python Project Best Practices

## 🔴 CRITICAL: Environment Activation

**ALWAYS activate the project's dedicated conda environment before ANY command execution.**

This project uses: **`fabric-cli-cicd`**

```bash
# Pattern to use for ALL commands
source ~/miniconda3/etc/profile.d/conda.sh && conda activate fabric-cli-cicd && {COMMAND}
```

### Finding the Environment Name

1. Check `environment.yml` for the environment name
2. Or run: `conda env list | grep -i {project_keyword}`
3. This project: `fabric-cli-cicd`

### ❌ NEVER Do This

- Run `pip install` in base environment
- Run `make` commands without activating env
- Assume the environment is already active
- **Provide user instructions WITHOUT conda activation steps**

### ✅ ALWAYS Include in User Instructions

When providing testing/usage instructions to the user, ALWAYS include:

```bash
# First, activate the conda environment
source ~/miniconda3/etc/profile.d/conda.sh && conda activate fabric-cli-cicd

# Then run commands...
```

---

## 🔴 CRITICAL: Prevent Regressions

### Before Making Changes

1. **Run tests first** to establish baseline:

   ```bash
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate {ENV} && make test
   ```

2. **Check git status** for clean working directory:

   ```bash
   git status
   ```

### After Making Changes

1. **Run tests again** to verify no regressions:

   ```bash
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate {ENV} && make test
   ```

2. **Run linting & formatting**:

   ```bash
   source ~/miniconda3/etc/profile.d/conda.sh && conda activate {ENV} && make lint
   ```

   *Runs `black .` (format) and `flake8 src` (check)*

3. **Commit incrementally** with descriptive messages

---

## Systematic Implementation Pattern

When implementing multiple changes:

1. **Phase 1**: Tests and validation (lowest risk)
   - Add new tests
   - Verify existing tests pass
   - No production code changes yet

2. **Phase 2**: Non-breaking additions
   - Add new files/modules
   - Add new optional parameters
   - Extend existing functionality

3. **Phase 3**: Modifications with test coverage
   - Modify existing code only after tests exist
   - Make one change at a time
   - Test after each change

4. **Phase 4**: Breaking changes (requires approval)
   - API changes
   - Configuration format changes
   - Dependency updates

---

## Git Workflow

// turbo

```bash
# Check status
git status

# Add changed files
git add -A

# Commit with conventional message
git commit -m "type: description"
# Types: feat, fix, docs, test, refactor, chore

# Push to origin
git push origin main
```

### For Multiple Remotes

```bash
# Check all remotes
git remote -v

# Switch accounts if needed
gh auth switch -u {ACCOUNT_NAME}

# Push to specific remote
git push {remote_name} main
```
