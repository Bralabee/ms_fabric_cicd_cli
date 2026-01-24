"""
USF Fabric CLI - Thin Wrapper for Microsoft Fabric CI/CD.

This package provides a lightweight CLI wrapper around the Microsoft Fabric CLI
for enterprise CI/CD workflows.
"""

__version__ = "1.5.0"
__author__ = "USF Fabric Team"

# Lazy imports to avoid circular dependency issues when running as module
def __getattr__(name):
    """Lazy import main components."""
    if name == "app":
        from usf_fabric_cli.cli import app
        return app
    elif name == "FabricDeployer":
        from usf_fabric_cli.services.deployer import FabricDeployer
        return FabricDeployer
    elif name == "FabricCLIError":
        from usf_fabric_cli.exceptions import FabricCLIError
        return FabricCLIError
    elif name == "FabricCLINotFoundError":
        from usf_fabric_cli.exceptions import FabricCLINotFoundError
        return FabricCLINotFoundError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "app",
    "FabricDeployer", 
    "FabricCLIError",
    "FabricCLINotFoundError",
    "__version__",
]

