# usf_fabric_cli_cicd Context & Rules

This is the central nervous system for the `usf_fabric_cli_cicd` project. Claude Code must read and adhere to these rules whenever operating in this directory.

## Project Architecture
- **Language:** Python 3.10+
- **Environment:** Always use a dedicated conda virtual environment. The dependencies are managed via `requirements.txt` and `environment.yml`.
- **Core Functionality:** This is a CLI application designed to interface with Microsoft Fabric for CI/CD operations (tracking producer/consumer code workflows).
- **Structure:**
  - `/src/usf_fabric_cli`: Core CLI application logic.
  - `/tests`: Unit and integration testing directory.
  - `/.github/workflows`: GitHub Actions for the CI/CD of the CLI itself.

## Workflow Rules
1. **Never Break Working Code:** Avoid breaking changes when progressing any development. Make it a routine to understand the project state, previous changes, and desired goal before modifying files.
2. **Be Thorough, Not Peripheral:** Ensure implementations are systems-oriented, not just spitting out code. Consider edge cases and user-facing CLI UX.
3. **Environment Aware:** This project is deployed across different environments (staging, test, prod). Ensure any configuration is environment-agnostic or properly handled via `.env` files.
4. **Testing:** Test regularly. You must run `make verify` or `pytest` after substantive changes.

## Automatic Skill Activation
Whenever you are asked to modify this codebase, you must proactively apply these skills if relevant:
- **`code-review`**: Before committing changes, review your own code.
- **`security-guidance`**: Ensure CLI inputs and subprocess commands avoid injections.
- **`mcp-builder`**: If asked to extend functionality connecting to external services, consider utilizing MCP paradigms.

## Documentation & Version Control
- Update `CHANGELOG.md` whenever adding features or fixing bugs.
- Always use the `get-shit-done` framework (`/gsd:new-project` -> `/gsd:execute-phase N`) when implementing new features or undertaking large refactors.
- Commit changes using atomic, descriptive Git messages. Use branching methodologies for feature development (e.g., `feature/cool-new-cli-command`).
