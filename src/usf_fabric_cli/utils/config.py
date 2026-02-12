"""
Configuration Management - Thin Wrapper Component 1/5
~50 LOC - Validates and manages project configurations

Key Learning Applied: Configuration over Code
- Make everything configurable for any organization
- Validate early to prevent deployment failures
- Environment-specific overrides
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from jsonschema import validate

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceConfig:
    """Workspace configuration for any organization/project"""

    name: str
    display_name: str
    description: str
    capacity_id: str
    domain: Optional[str] = None

    # Git integration
    git_repo: Optional[str] = None
    git_branch: str = "main"
    git_directory: str = "/"

    # Folder structure
    folders: Optional[List[str]] = None

    # Items to create
    lakehouses: Optional[List[Dict[str, Any]]] = None
    warehouses: Optional[List[Dict[str, Any]]] = None
    notebooks: Optional[List[Dict[str, Any]]] = None
    pipelines: Optional[List[Dict[str, Any]]] = None
    semantic_models: Optional[List[Dict[str, Any]]] = None

    # Generic resources (Future-proof)
    resources: Optional[List[Dict[str, Any]]] = None

    # Principals (users/service principals to add)
    principals: Optional[List[Dict[str, str]]] = None

    # Deployment Pipeline configuration
    deployment_pipeline: Optional[Dict[str, Any]] = None


class ConfigManager:
    """Manages configuration loading and validation"""

    def __init__(self, config_path: str, validate_env: bool = True):
        self.config_path = Path(config_path)
        self.schema = self._load_schema()
        # Ensure env vars are loaded
        get_environment_variables(validate_vars=validate_env)

    def load_config(self, environment: Optional[str] = None) -> WorkspaceConfig:
        """Load and validate configuration"""
        # Load base config
        if not self.config_path.exists():
            # Try looking in config/ directory if path was just filename
            if not str(self.config_path).startswith("config/"):
                alt_path = Path("config") / self.config_path.name
                if alt_path.exists():
                    self.config_path = alt_path

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            content = f.read()
            content = self._substitute_env_vars(content)
            config_data = yaml.safe_load(content)

        # Apply environment overrides (inline block takes priority over external files)
        if environment:
            # Check for inline 'environments' block first
            inline_envs = config_data.get("environments", {})
            if environment in inline_envs:
                env_config = inline_envs[environment]
                logger.info("Applying inline environment override: %s", environment)
            else:
                env_config = self._load_environment_config(environment)
            config_data = self._merge_configs(config_data, env_config)

        # Remove 'environments' meta-key before schema validation
        # (it's a config convenience, not a deployment property)
        config_data.pop("environments", None)

        # Validate against schema
        validate(instance=config_data, schema=self.schema)

        # Convert to WorkspaceConfig
        return self._to_workspace_config(config_data)

    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in format ${VAR_NAME}"""
        pattern = re.compile(r"\$\{([^}^{]+)\}")

        def replace(match):
            var_name = match.group(1)
            value = os.getenv(var_name)

            # Sanitize env vars to remove inline comments
            if value and "#" in value:
                value = value.split("#")[0].strip()

            if value is None:
                # Don't fail yet, let validation catch it or leave as is
                return match.group(0)
            return value

        return pattern.sub(replace, content)

    def _load_environment_config(self, environment: Optional[str]) -> Dict[str, Any]:
        """Load environment-specific overrides"""
        # Strategy 1: Look for 'environments' folder at the project root
        # (config/environments)
        # We assume the config file is somewhere inside config/
        # (e.g. config/projects/Org/proj.yaml)

        # Walk up the tree until we find 'config' directory
        current_path = self.config_path.parent
        config_root = None

        # Try to find the 'config' root directory
        for _ in range(4):  # Limit depth
            if current_path.name == "config":
                config_root = current_path
                break
            if (current_path / "environments").exists():
                config_root = current_path
                break
            current_path = current_path.parent

        if not config_root:
            # Fallback: assume relative path from current working directory
            if Path("config/environments").exists():
                config_root = Path("config")
            else:
                # Last resort: try standard relative paths
                env_path = (
                    self.config_path.parent.parent
                    / "environments"
                    / f"{environment}.yaml"
                )
                if env_path.exists():
                    return self._read_yaml(env_path)
                return {}

        env_path = config_root / "environments" / f"{environment}.yaml"

        if env_path.exists():
            return self._read_yaml(env_path)

        return {}

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        """Helper to read and substitute YAML"""
        with open(path, "r") as f:
            content = f.read()
            content = self._substitute_env_vars(content)
            return yaml.safe_load(content)

    def _merge_configs(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge base config with environment overrides"""
        result = base.copy()
        for key, value in override.items():
            if (
                isinstance(value, dict)
                and key in result
                and isinstance(result[key], dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            elif (
                isinstance(value, list)
                and key in result
                and isinstance(result[key], list)
            ):
                # Merge lists instead of replacing (e.g. for principals)
                # We'll deduplicate later in _to_workspace_config
                result[key] = result[key] + value
            else:
                result[key] = value
        return result

    def _to_workspace_config(self, data: Dict[str, Any]) -> WorkspaceConfig:
        """Convert dict to WorkspaceConfig dataclass"""
        workspace_data = data.get("workspace", {})

        # Start with principals from config (merged project + env)
        raw_principals = data.get("principals", [])

        # Helper to check if ID exists
        existing_ids = {p.get("id") for p in raw_principals if p.get("id")}

        final_principals = list(raw_principals)

        # Inject mandatory principals from environment variables
        # (if not already present)

        # Add Additional Admin
        additional_admin = os.getenv("ADDITIONAL_ADMIN_PRINCIPAL_ID")
        if additional_admin and additional_admin not in existing_ids:
            final_principals.append(
                {
                    "id": additional_admin,
                    "role": "Admin",
                    "description": "Mandatory Additional Admin",
                }
            )
            existing_ids.add(additional_admin)

        # Add Additional Contributor
        additional_contributor = os.getenv("ADDITIONAL_CONTRIBUTOR_PRINCIPAL_ID")
        if additional_contributor and additional_contributor not in existing_ids:
            final_principals.append(
                {
                    "id": additional_contributor,
                    "role": "Contributor",
                    "description": "Mandatory Additional Contributor",
                }
            )
            existing_ids.add(additional_contributor)

        # Final deduplication by ID (just in case merge created duplicates)
        unique_principals = []
        seen_ids = set()
        for p in final_principals:
            pid = p.get("id")
            if pid and pid not in seen_ids:
                unique_principals.append(p)
                seen_ids.add(pid)
            elif not pid:
                # Keep entries without ID (though invalid, we let schema validation
                # handle it)
                unique_principals.append(p)

        return WorkspaceConfig(
            name=workspace_data["name"],
            display_name=workspace_data.get("display_name", workspace_data["name"]),
            description=workspace_data.get("description", ""),
            capacity_id=workspace_data["capacity_id"],
            domain=workspace_data.get("domain"),
            git_repo=workspace_data.get("git_repo"),
            git_branch=workspace_data.get("git_branch", "main"),
            git_directory=workspace_data.get("git_directory", "/"),
            folders=data.get(
                "folders", ["Bronze", "Silver", "Gold", "Notebooks", "Pipelines"]
            ),
            lakehouses=data.get("lakehouses", []),
            warehouses=data.get("warehouses", []),
            notebooks=data.get("notebooks", []),
            pipelines=data.get("pipelines", []),
            semantic_models=data.get("semantic_models", []),
            resources=data.get("resources", []),
            principals=unique_principals,
            deployment_pipeline=data.get("deployment_pipeline"),
        )

    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema for configuration validation"""
        # Schema is in src/schemas/workspace_config.json
        # __file__ is src/usf_fabric_cli/config.py -> parent is src/core ->
        # parent.parent is src
        base_path = Path(__file__).resolve().parent.parent
        schema_path = base_path / "schemas" / "workspace_config.json"

        if schema_path.exists():
            with open(schema_path, "r") as f:
                return json.load(f)

        # Basic schema if file doesn't exist
        return {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "capacity_id": {"type": "string"},
                    },
                    "required": ["name", "capacity_id"],
                }
            },
            "required": ["workspace"],
        }


def get_environment_variables(validate_vars: bool = True) -> Dict[str, str]:
    """
    Get required environment variables with validation.

    Args:
        validate_vars: If True, raises ValueError if required variables are missing.

    DEPRECATED: Use core.secrets.get_secrets() instead for new code.
    This function is maintained for backward compatibility.
    """
    # Load variables from .env to simplify local workflows
    load_dotenv()

    # Try the new secrets module first
    try:
        from usf_fabric_cli.utils.secrets import (
            get_environment_variables as get_secrets_env,
        )

        return get_secrets_env()
    except ImportError:
        # Fallback to legacy behavior if secrets module not available
        pass

    # If FABRIC_TOKEN is not found, try looking for .env files in config directory
    if not os.getenv("FABRIC_TOKEN") and not os.getenv("AZURE_CLIENT_ID"):
        # Try CWD config first
        config_env_files = list(Path("config").glob("*.env"))

        # If not found, try relative to this file (project root/config)
        if not config_env_files:
            project_root = Path(__file__).resolve().parent.parent.parent
            config_dir = project_root / "config"
            if config_dir.exists():
                config_env_files = list(config_dir.glob("*.env"))

        if config_env_files:
            # Load the first found env file
            logger.info("Loading environment from %s", config_env_files[0])
            load_dotenv(config_env_files[0])

    # Map Azure standard names to internal names if needed
    if os.getenv("AZURE_TENANT_ID") and not os.getenv("TENANT_ID"):
        os.environ["TENANT_ID"] = os.getenv("AZURE_TENANT_ID")

    # Auto-generate token from Service Principal if provided but token is missing
    if (
        not os.getenv("FABRIC_TOKEN")
        and os.getenv("AZURE_CLIENT_ID")
        and os.getenv("AZURE_CLIENT_SECRET")
    ):
        try:
            from azure.identity import ClientSecretCredential

            logger.info("Generating Fabric token from Service Principal credentials...")
            tenant = os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID")
            client = os.getenv("AZURE_CLIENT_ID")
            secret = os.getenv("AZURE_CLIENT_SECRET")
            if not tenant or not client or not secret:
                raise ValueError("Missing required credentials")
            credential = ClientSecretCredential(
                tenant_id=tenant,
                client_id=client,
                client_secret=secret,
            )
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            os.environ["FABRIC_TOKEN"] = token.token
            logger.info("Fabric token generated successfully")
        except Exception as e:
            logger.warning("Failed to generate token from Service Principal: %s", e)

    # If validation is disabled, return current env immediately
    if not validate_vars:
        return {
            "FABRIC_TOKEN": os.getenv("FABRIC_TOKEN", ""),
            "TENANT_ID": os.getenv("TENANT_ID", ""),
        }

    required_vars = [
        "FABRIC_TOKEN",
        "TENANT_ID",
    ]

    env_vars = {}
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if value:
            env_vars[var] = value
        else:
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return env_vars
