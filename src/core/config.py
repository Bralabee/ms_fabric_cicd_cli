"""
Configuration Management - Thin Wrapper Component 1/5
~50 LOC - Validates and manages project configurations

Key Learning Applied: Configuration over Code
- Make everything configurable for any organization
- Validate early to prevent deployment failures
- Environment-specific overrides
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
import yaml
from dotenv import load_dotenv
from jsonschema import validate


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
    folders: List[str] = None

    # Items to create
    lakehouses: List[Dict[str, Any]] = None
    warehouses: List[Dict[str, Any]] = None
    notebooks: List[Dict[str, Any]] = None
    pipelines: List[Dict[str, Any]] = None
    semantic_models: List[Dict[str, Any]] = None

    # Generic resources (Future-proof)
    resources: List[Dict[str, Any]] = None

    # Principals (users/service principals to add)
    principals: List[Dict[str, str]] = None


class ConfigManager:
    """Manages configuration loading and validation"""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.schema = self._load_schema()
        # Ensure env vars are loaded
        get_environment_variables()

    def load_config(self, environment: str = None) -> WorkspaceConfig:
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

        # Apply environment overrides
        if environment:
            env_config = self._load_environment_config(environment)
            config_data = self._merge_configs(config_data, env_config)

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
            if value is None:
                print(
                    f"ℹ️  Note: Value for '{var_name}' not provided. Proceeding without it."
                )
                return ""
            return value

        return pattern.sub(replace, content)

    def _load_environment_config(self, environment: str) -> Dict[str, Any]:
        """Load environment-specific overrides"""
        # Try standard structure: config/templates/../environments/env.yaml
        env_path = (
            self.config_path.parent.parent / "environments" / f"{environment}.yaml"
        )

        if not env_path.exists():
            # Try subdirectory: config/environments/env.yaml (if config is in config/)
            env_path = self.config_path.parent / "environments" / f"{environment}.yaml"

        if env_path.exists():
            with open(env_path, "r") as f:
                content = f.read()
                content = self._substitute_env_vars(content)
                return yaml.safe_load(content)
        return {}

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
            else:
                result[key] = value
        return result

    def _to_workspace_config(self, data: Dict[str, Any]) -> WorkspaceConfig:
        """Convert dict to WorkspaceConfig dataclass"""
        workspace_data = data.get("workspace", {})
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
            principals=data.get("principals", []),
        )

    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema for configuration validation"""
        # Schema is in src/schemas/workspace_config.json
        # __file__ is src/core/config.py -> parent is src/core -> parent.parent is src
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


def get_environment_variables() -> Dict[str, str]:
    """
    Get required environment variables with validation.

    DEPRECATED: Use core.secrets.get_secrets() instead for new code.
    This function is maintained for backward compatibility.
    """
    # Load variables from .env to simplify local workflows
    load_dotenv()

    # Try the new secrets module first
    try:
        from core.secrets import get_environment_variables as get_secrets_env

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
            print(f"Loading environment from {config_env_files[0]}")
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

            print("Generating Fabric token from Service Principal credentials...")
            credential = ClientSecretCredential(
                tenant_id=os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            )
            token = credential.get_token("https://api.fabric.microsoft.com/.default")
            os.environ["FABRIC_TOKEN"] = token.token
            print("✅ Fabric token generated successfully")
        except Exception as e:
            print(f"⚠️ Failed to generate token from Service Principal: {e}")

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
