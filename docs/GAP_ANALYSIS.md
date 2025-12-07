# Architectural Gap Analysis & Alignment Report

## 1. Configuration Architecture
**Current State:**
- **Source of Truth:** `config/project.yaml` (Human-readable, supports comments & variables).
- **Secrets/Environment:** `.env` (Injects values into YAML variables like `${FABRIC_CAPACITY_ID}`).
- **Validation:** `src/schemas/workspace_config.json` (Technical schema to validate YAML structure).

**Alignment Check:**
- ✅ **Separation of Concerns:** Config (YAML) is separated from Secrets (.env) and Logic (Python).
- ✅ **Validation:** JSON Schema ensures the YAML is valid before deployment starts.
- ✅ **Multi-Org Support:** Configuration templates now use generic variable names (e.g., `${ADDITIONAL_ADMIN_PRINCIPAL_ID}`) instead of hardcoded organization-specific IDs, allowing for seamless reuse across different tenants.

## 2. Functional Gaps (Fabric Wrapper)
The `FabricCLIWrapper` is a "thin wrapper" around the `fab` CLI. Current limitations:

| Feature | Status | Gap Description |
|---------|--------|-----------------|
| **Git Integration** | ✅ Implemented | Supports both Azure DevOps and GitHub via `fab api` calls. |
| **Folder Support** | ✅ Implemented | Items are now correctly placed in folders using `mkdir Workspace/Folder/Item`. |
| **Generic Resources** | ✅ Implemented | "Future-proof" support for any Fabric item type via `resources` config. |
| **Idempotency** | 🟢 Robust | Uses `fab exists` checks before creation to avoid error parsing fragility. |
| **UX Improvements** | ✅ Implemented | Added visual progress indicators and wait steps for propagation delays. |
| **State Management** | 🔴 Missing | No state file (like Terraform). Renaming an item in YAML creates a duplicate; the old one is orphaned. |

## 3. Deployment Logic
**Current State:**
- `fabric_deploy.py` orchestrates the deployment linearly.
- It handles Authentication (Service Principal), Folder Creation, and Item Creation (Specific & Generic).

**Alignment Check:**
- ✅ **Authentication:** Fixed. Now uses explicit Service Principal login.
- ✅ **Resilience:** Retries on capacity assignment failure.
- ✅ **Flexibility:** Supports any Fabric item type without code changes.
- ✅ **Config Robustness:** Gracefully handles missing optional environment variables by skipping the associated resources (e.g., optional admins) instead of failing.
- ⚠️ **Error Handling:** If a deployment fails halfway, there is no "rollback" mechanism.

## 4. Recommendations
1.  **State Tracking:** Consider a simple `.state.json` to track created Resource IDs against Config Names to detect drift/renames.
2.  **Cleanup:** Remove legacy JSON config files from the workspace to avoid confusion.

## 5. Next Steps
- **Future:** Implement State Tracking (`.state.json`) to handle renames and drift detection.
- **Future:** Add rollback capabilities for failed deployments.
