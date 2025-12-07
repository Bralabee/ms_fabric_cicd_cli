# Fabric CLI CI/CD Framework - User Guide

## 1. Introduction

The Fabric CLI CI/CD Framework automates Microsoft Fabric workspace lifecycle management through configuration-driven deployment. This framework eliminates manual portal operations by translating declarative YAML configurations into fully provisioned environments. Users specify infrastructure requirements once, and the framework handles creation, updates, and ongoing maintenance.

**Key Capabilities:**
*   **Infrastructure as Code**: Define complete Fabric environments (Workspaces, Lakehouses, Warehouses, Pipelines) using a single configuration file.
*   **Automated Security**: Systematically assign users, groups, and service principals with appropriate permissions.
*   **Standardization**: Enforce consistent folder structures and naming conventions across projects.
*   **Multi-Environment Support**: Deploy consistent configurations to Development, Testing, and Production environments with environment-specific settings.
*   **Git Integration**: Connect workspaces to Git repositories for version control.
*   **Domain Management**: Assign workspaces to specific business domains (e.g., "Finance", "Sales").

---

## 2. Configuration Architecture

The framework operates from declarative YAML configuration files that define complete Fabric environments as infrastructure as code.

### Configuration Structure (`config/your-project.yaml`)

Each configuration file contains five core sections that comprehensively define workspace requirements:

#### A. Workspace Definition
Defines the primary container for the project.
```yaml
workspace:
  name: "Finance_Analytics_Hub"
  display_name: "Finance Analytics Hub"
  description: "Central hub for all financial reporting"
  capacity_id: "${FABRIC_CAPACITY_ID}"  # References environment setting
  domain: "01 Strategy, Governance & Compliance" # Assigns to a Fabric Domain
```

#### B. Organization (Folders)
Establishes the folder structure for workspace organization.
```yaml
folders:
  - "01_Raw_Data"
  - "02_Transformation"
  - "03_Gold_Reports"
  - "99_Admin"
```

#### C. Infrastructure (Items)
Specifies the Fabric items to be created and their location within the folder structure.
```yaml
lakehouses:
  - name: "Finance_Raw"
    folder: "01_Raw_Data"
    description: "Landing zone for raw SAP data"

warehouses:
  - name: "Finance_Gold"
    folder: "03_Gold_Reports"
    description: "Curated data for Power BI reporting"

pipelines:
  - name: "Ingest_SAP_Daily"
    folder: "02_Transformation"
```

#### D. Security (Principals)
Controls access permissions for the workspace.
```yaml
principals:
  # Admin Access
  - id: "${DEV_ADMIN_OBJECT_ID}"
    role: "Admin"
  
  # Team Access (Read/Write)
  - id: "${DEV_MEMBERS_OBJECT_ID}" # Supports lists of users
    role: "Member"
    
  # Viewer Access (Read Only)
  - id: "finance-viewers-group@yourcompany.com"
    role: "Viewer"
```

#### E. Version Control (Git)
Configures the connection to Azure DevOps or GitHub.
```yaml
workspace:
  # ... other settings ...
  git_repo: "https://dev.azure.com/YourOrg/FinanceProject/_git/RepoName"
  git_branch: "main"
  git_directory: "/fabric-workspace"
```

---

## 3. Operational Procedures

### Step 1: Environment Configuration

Configure authentication and environment variables in the `.env` file. This file manages sensitive credentials through the 12-Factor App configuration pattern.

**Required Credentials:**
- **AZURE_CLIENT_ID**: Service Principal application identifier for API authentication
- **AZURE_CLIENT_SECRET**: Service Principal credential value
- **TENANT_ID**: Azure AD tenant identifier
- **FABRIC_CAPACITY_ID**: Target Fabric capacity resource identifier
- **DEV_ADMIN_OBJECT_ID**: Primary administrator principal identifier

### Step 2: Project Generation
Use the provided script to generate a new project configuration. This script prompts for the Client Name, Project Name, and Capacity ID.

**Command Syntax:**
```bash
python scripts/generate_project.py "Client Name" "Project Name" --capacity-id "YOUR_CAPACITY_ID"
```

**Example:**
To create a "Sales" project for client "Contoso" using Capacity ID `F64-12345`:

1.  Execute the command:
    ```bash
    python scripts/generate_project.py "Contoso" "Sales" --capacity-id "F64-12345"
    ```

2.  **Outcome:**
    *   A directory is created: `config/contoso/`
    *   A configuration file is generated: `config/contoso/sales.yaml`
    *   The file is populated with a standard best-practice template.

3.  **Customization**:
    *   Open `config/contoso/sales.yaml`.
    *   **Review**: Adjust folder names as required (e.g., "01_Raw" vs "01_Bronze").
    *   **Security**: Verify that principal IDs match the intended users or groups.
    *   **Save** the file.

### Step 3: Deployment
Execute the deployment command to apply the configuration.

```bash
make deploy config=config/MyClient/SalesProject.yaml env=dev
```

**Execution Process:**
1.  **Configuration Merge**: The tool combines the project blueprint (`config/contoso/sales.yaml`) with environment-specific settings (`config/environments/dev.yaml`) to ensure appropriate security configurations.
2.  **Authentication**: Secure login to Fabric is established.
3.  **Validation**: The configuration is checked for errors.
4.  **Workspace Verification**: The tool checks for the existence of the workspace.
    *   *If absent*: The workspace is created.
    *   *If present*: The workspace is updated (idempotent operation).
5.  **Folder Structure**: Missing folders are created.
6.  **Item Creation**: Missing Lakehouses, Warehouses, and other items are provisioned.
7.  **Security Synchronization**: Users and permissions are updated.
8.  **Domain Synchronization**: The workspace is assigned to the specified Domain.
9.  **Git Synchronization**: The workspace is connected to the configured Git repository.

### Step 4: Verification
Access the Microsoft Fabric Portal to confirm that the workspace has been configured correctly with the expected folders, items, and user assignments.

---

## 4. Advanced Capabilities

### A. Multi-Environment Deployment
The same configuration file can be deployed to Development, Staging, and Production environments using environment overrides.

*   **Development**: `make deploy config=... env=dev` (Uses Dev users, lower capacity)
*   **Production**: `make deploy config=... env=prod` (Uses Prod users, higher capacity, stricter security)

### B. Diagnostics
Run diagnostic checks to verify system health.
```bash
make diagnose
```
*Checks performed: Internet connection, Fabric API access, Token validity, CLI installation.*

### C. Migration Analysis
Analyze existing manual setups for migration to the automated tool:
```bash
python scripts/analyze_migration.py /path/to/your/code
```
*This provides an assessment of automation potential for current setups.*

### D. Decommissioning (Destroy)
To remove a workspace (e.g., a temporary test environment):
```bash
make destroy config=config/MyClient/SalesProject.yaml env=dev
```
*Note: This operation permanently deletes the workspace and all associated data.*

---

## 5. Troubleshooting

| Issue | Probable Cause | Resolution |
| :--- | :--- | :--- |
| **"Unauthorized" / "Access Denied"** | The Service Principal lacks necessary permissions. | Request IT to assign the "Fabric Admin" or "Domain Contributor" role to the Service Principal. |
| **"Capacity not found"** | The ID in `.env` is incorrect. | Verify `FABRIC_CAPACITY_ID` in the `.env` file. |
| **"Domain assignment failed"** | Service Principal is not a Domain Contributor. | Add the Service Principal in Fabric Admin Portal -> Domains -> Manage Access. |
| **"Git connection failed"** | Incorrect Repo URL or insufficient access. | Verify the `git_repo` URL in the YAML file and ensure the Service Principal has access to the repository. |

---

## 6. Summary Checklist

- [ ] **Define**: Create the YAML configuration in `config/`.
- [ ] **Configure**: Verify `.env` contains correct IDs.
- [ ] **Deploy**: Execute `make deploy`.
- [ ] **Verify**: Inspect the Fabric Portal.

This tool transforms Fabric management from a manual task into a reliable, automated process.

---

## 7. Glossary

*   **Blueprint (YAML)**: A text file describing the desired state of the workspace.
*   **Capacity ID**: A unique identifier for the compute resources allocated to the workspace.
*   **Service Principal**: A non-interactive identity used for automated authentication.
*   **Environment (Dev/Prod)**: Distinct deployment targets (e.g., Development for testing, Production for live business operations).
*   **Idempotent**: A property ensuring that an operation can be applied multiple times without changing the result beyond the initial application.

