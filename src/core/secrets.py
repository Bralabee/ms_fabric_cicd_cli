"""
Enterprise secrets management with waterfall configuration loading.

Priority hierarchy:
1. Environment variables (production/CI/CD)
2. .env file (local development)
3. Error on missing required credentials

Implements 12-Factor App configuration methodology for secure credential management
across development, staging, and production environments.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class FabricSecrets(BaseSettings):
    """
    Pydantic-based configuration for Microsoft Fabric authentication.

    Loads credentials in priority order: environment variables, .env file.
    Supports Service Principal authentication and direct token authentication.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Service Principal Authentication (optional - validation happens in methods)
    azure_client_id: Optional[str] = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: Optional[str] = Field(
        default=None, alias="AZURE_CLIENT_SECRET"
    )
    tenant_id: Optional[str] = Field(default=None, alias="TENANT_ID")

    # Fabric Access Token (optional, for direct token auth)
    fabric_token: Optional[str] = Field(default=None, alias="FABRIC_TOKEN")

    # Git Authentication (optional)
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    azure_devops_pat: Optional[str] = Field(default=None, alias="AZURE_DEVOPS_PAT")

    @field_validator("tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v):
        """Normalize TENANT_ID or AZURE_TENANT_ID to tenant_id field."""
        if v:
            return v
        return os.getenv("AZURE_TENANT_ID") or v

    def get_tenant_id(self) -> Optional[str]:
        """Returns configured tenant ID."""
        return self.tenant_id

    def validate_service_principal(self) -> bool:
        """Returns True if all Service Principal credentials are configured."""
        return bool(
            self.azure_client_id and self.azure_client_secret and self.tenant_id
        )

    def validate_fabric_token(self) -> bool:
        """Returns True if Fabric token is configured."""
        return bool(self.fabric_token)

    def validate_fabric_auth(self) -> tuple[bool, str]:
        """
        Validates configured authentication method (Service Principal or direct token).

        Returns:
            (is_valid, error_message) tuple
        """
        if self.fabric_token:
            return (True, "")

        if self.validate_service_principal():
            return (True, "")

        missing = []
        if not self.azure_client_id:
            missing.append("AZURE_CLIENT_ID")
        if not self.azure_client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        if not self.tenant_id:
            missing.append("TENANT_ID")

        error_msg = f"Missing Fabric authentication credentials: {', '.join(missing)}"
        return (False, error_msg)

    def validate_git_auth(self, provider: str = "github") -> tuple[bool, str]:
        """
        Validates Git provider authentication credentials.

        Args:
            provider: 'github' or 'azure_devops'

        Returns:
            (is_valid, error_message) tuple
        """
        if provider.lower() == "github":
            if self.github_token:
                return (True, "")
            return (False, "Missing GitHub authentication token (GITHUB_TOKEN)")
        elif provider.lower() in ["azuredevops", "azure_devops", "ado"]:
            if self.azure_devops_pat:
                return (True, "")
            return (False, "Missing Azure DevOps PAT (AZURE_DEVOPS_PAT)")
        return (False, f"Unknown Git provider: {provider}")

    def is_ci_environment(self) -> bool:
        """Returns True if running in continuous integration environment."""
        ci_indicators = [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_HOME",
            "AZURE_PIPELINES",
        ]
        return any(os.getenv(indicator) for indicator in ci_indicators)

    def to_env_dict(self) -> dict:
        """Exports configuration as environment variable dictionary."""
        return {
            "AZURE_CLIENT_ID": self.azure_client_id or "",
            "AZURE_CLIENT_SECRET": self.azure_client_secret or "",
            "TENANT_ID": self.tenant_id or "",
            "FABRIC_TOKEN": self.fabric_token or "",
            "GITHUB_TOKEN": self.github_token or "",
            "AZURE_DEVOPS_PAT": self.azure_devops_pat or "",
        }

    @classmethod
    def load_with_fallback(cls) -> "FabricSecrets":
        """
        Instantiates secrets configuration, loading available credentials without validation.

        Returns:
            FabricSecrets instance
        """
        return cls()


def get_secrets() -> FabricSecrets:
    """
    Loads and validates Fabric authentication credentials.

    Returns:
        Validated FabricSecrets instance

    Raises:
        ValueError: When required authentication credentials are missing
    """
    secrets = FabricSecrets()
    is_valid, error_msg = secrets.validate_fabric_auth()

    if not is_valid:
        raise ValueError(error_msg)

    return secrets


def get_environment_variables() -> dict:
    """
    Returns environment variables dictionary for legacy code compatibility.

    Attempts secrets module first, falls back to direct environment variable access.

    Returns:
        Dictionary of environment variables
    """
    try:
        secrets = get_secrets()
        return secrets.to_env_dict()
    except Exception:
        # Fallback to legacy environment variable loading
        return {
            "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID", ""),
            "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET", ""),
            "TENANT_ID": os.getenv("TENANT_ID") or os.getenv("AZURE_TENANT_ID", ""),
            "FABRIC_TOKEN": os.getenv("FABRIC_TOKEN", ""),
            "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
            "AZURE_DEVOPS_PAT": os.getenv("AZURE_DEVOPS_PAT", ""),
        }


# For convenience imports
__all__ = ["FabricSecrets", "get_secrets", "get_environment_variables"]
