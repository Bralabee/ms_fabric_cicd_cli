# Data Product Factory: Automated Workspace & Git Integration Guide

## Executive Summary

This guide outlines the **"Data Product Factory"** workflow using the `usf_fabric_cli_cicd` solution. It demonstrates how to automate the lifecycle of a Microsoft Fabric data product—from initial onboarding to feature-isolated development—while enforcing strict governance and naming standards.

**Target Audience:** Data Platform Engineers, Analytics Engineers, and DevOps Leads.

**Key Capabilities Demonstrated:**
*   **Zero-Touch Provisioning:** Creating workspaces via CLI/API without manual portal interaction.
*   **Git-First Governance:** Automatically binding Fabric workspaces to specific Git repositories and branches.
*   **Environment Isolation:** Seamlessly spinning up ephemeral "Feature Workspaces" for safe development.
*   **Standardization:** Enforcing folder structures and naming conventions via configuration templates.

---

## 1. Prerequisites

Before executing the workflows in this guide, ensure the following requirements are met:

*   **Environment:**
    *   Access to a Linux/WSL terminal with Python 3.11+.
    *   The `fabric-cli-cicd` Conda environment is active.
*   **Credentials:**
    *   A `.env` file configured with your Service Principal credentials (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`).
    *   A valid **Fabric Capacity ID** (F-SKU or Trial).
*   **Version Control:**
    *   A target Git repository (Azure DevOps or GitHub) initialized and accessible.
    *   Permissions to create branches and push code.

---

## 2. Workflow Overview

The "Data Product Factory" follows a strict lifecycle to ensure stability in `DEV` while allowing flexibility in `FEATURE` branches.

```mermaid
graph LR
    A[Config Definition] -->|Trigger| B(Deploy Script)
    B -->|Provision| C[Fabric Workspace]
    B -->|Bind| D[Git Repository]
    
    subgraph "DEV Environment"
    C_DEV[Workspace: Product [DEV]] <-->|Sync| D_MAIN[Branch: main]
    end
    
    subgraph "FEATURE Environment"
    C_FEAT[Workspace: Product [Feat 123]] <-->|Sync| D_FEAT[Branch: feature/123]
    end
```

---

## 3. Phase 1: Product Definition (Configuration)

The foundation of the factory is the **Configuration File**. This YAML file acts as the "blueprint" for your data product.

**Action:** Create a new file at `config/products/sales_analytics.yaml`.

**Content:**
```yaml
project_name: "SalesAnalytics"

# Global Settings
# Replace with your actual Fabric Capacity ID
capacity_id: "00000000-0000-0000-0000-000000000000" 

environments:
  # 1. The Stable DEV Environment (Linked to Main)
  dev:
    workspace_name: "SalesAnalytics [DEV]"
    description: "Development environment for Sales Analytics product"
    git_integration:
      enabled: true
      organization: "your-org-name"
      project: "your-project-name"
      repository: "sales-analytics-repo"
      branch: "main"
      directory: "/sales-analytics-dev"

  # 2. The Feature Branch Template (Dynamic)
  feature_123:
    workspace_name: "SalesAnalytics [Feature 123]"
    description: "Isolated feature workspace for Ticket #123"
    git_integration:
      enabled: true
      organization: "your-org-name"
      project: "your-project-name"
      repository: "sales-analytics-repo"
      branch: "feature/123"
      directory: "/sales-analytics-feature-123"
```

> **Note:** Ensure the `organization`, `project`, and `repository` fields match your actual Azure DevOps/GitHub setup.

---

## 4. Phase 2: Deploying the DEV Environment

This step fulfills the requirement to **automatically create a DEV workspace** and **link it to the MAIN Git repo**.

**Command:**
```bash
python src/fabric_deploy.py deploy \
  --config config/products/sales_analytics.yaml \
  --environment dev
```

**What Happens Behind the Scenes:**
1.  **Authentication:** The CLI authenticates using the Service Principal.
2.  **Idempotency Check:** It checks if `SalesAnalytics [DEV]` exists. If not, it creates it assigned to the specified Capacity.
3.  **Git Binding:** It calls the Fabric REST API to connect the workspace to the `main` branch of your repository.
4.  **Initialization:** It initializes the remote folder structure (`/sales-analytics-dev`) if it doesn't exist.

---

## 5. Phase 3: The Feature Branch Workflow

This phase demonstrates **Environment Isolation**. A developer needs to work on a new feature ("Feature 123") without risking the stability of the DEV environment.

### Step 3.1: Create the Feature Branch
Use the tool's built-in Git manager to ensure the branch is created correctly locally.

**Command:**
```bash
python -c "from src.core.git_integration import GitManager; GitManager('.').create_branch('feature/123')"
```

### Step 3.2: Provision the Feature Workspace
Deploy a dedicated workspace linked specifically to this new feature branch.

**Command:**
```bash
python src/fabric_deploy.py deploy \
  --config config/products/sales_analytics.yaml \
  --environment feature_123
```

**Key Benefits:**
*   **Isolation:** Changes in `SalesAnalytics [Feature 123]` do not affect `SalesAnalytics [DEV]`.
*   **Traceability:** The workspace is explicitly named after the feature ticket.
*   **Sync:** The workspace is pre-wired to the `feature/123` branch, enabling immediate commit/sync operations from the Fabric UI.

---

## 6. Phase 4: Enforcing Standards (Templating)

To ensure that every environment looks the same, we use the **Templating Engine**. This prevents "configuration drift" where Feature workspaces lack the settings of Dev.

**Action:** Validate that the workspace adheres to the defined template.

**Command:**
```bash
python src/fabric_deploy.py validate \
  --config config/products/sales_analytics.yaml \
  --environment feature_123
```

*In a full CI/CD pipeline, this step would also deploy standard artifacts (e.g., a "Bronze Lakehouse") using `src/core/templating.py` to ensure the folder structure matches the corporate standard.*

---

## 7. Phase 5: Verification

To confirm the process was successful, perform the following checks:

### 7.1 Fabric Portal Check
1.  Log in to Microsoft Fabric.
2.  Navigate to **Workspaces**.
3.  Verify two workspaces exist:
    *   `SalesAnalytics [DEV]`
    *   `SalesAnalytics [Feature 123]`
4.  Open `SalesAnalytics [Feature 123]` -> **Workspace Settings** -> **Git Integration**.
5.  Confirm it is **Connected** to branch `feature/123`.

### 7.2 Repository Check
1.  Navigate to your Git provider (Azure DevOps/GitHub).
2.  Switch to branch `main`. Verify the folder `sales-analytics-dev` exists.
3.  Switch to branch `feature/123`. Verify the folder `sales-analytics-feature-123` exists.

---

## 8. Troubleshooting

| Issue | Possible Cause | Remediation |
| :--- | :--- | :--- |
| **"Workspace already exists"** | The script is idempotent, but if you need a fresh start, the workspace must be deleted manually or via CLI. | Run `fab workspace delete --name "SalesAnalytics [DEV]"` (use with caution). |
| **"Git connection failed"** | Invalid credentials or repository URL in `yaml`. | Verify the `git_integration` block in your config file matches your Git provider exactly. |
| **"Capacity not found"** | The `capacity_id` in config is invalid or the SP lacks permissions. | Ensure the Service Principal is an admin on the Fabric Capacity. |

---

## Conclusion

By following this guide, you have successfully implemented a **Data Product Factory**. You can now spin up standardized, Git-integrated environments on demand, significantly reducing manual overhead and increasing deployment reliability.
