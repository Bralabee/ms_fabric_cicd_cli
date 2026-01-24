"""
USF Fabric CLI - Thin Wrapper for Microsoft Fabric CI/CD.

This package provides a lightweight CLI wrapper around the Microsoft Fabric CLI
for enterprise CI/CD workflows.
"""

__version__ = "1.4.0"
__author__ = "USF Fabric Team"

# Re-export main components for convenience
from usf_fabric_cli.cli import app, FabricDeployer
from usf_fabric_cli.exceptions import FabricCLIError, FabricCLINotFoundError

# Backward compatibility: Allow imports from old 'core' package paths
import sys

# Register this package as 'core' for backward compatibility
# This allows existing code using 'from core.X import Y' to continue working
_current_module = sys.modules[__name__]

# Create backward-compatible module aliases
class _BackwardCompatModule:
    """Proxy module for backward compatibility."""
    
    def __init__(self, target_module):
        self._target = target_module
    
    def __getattr__(self, name):
        return getattr(self._target, name)

# Only set up backward compat if 'core' isn't already imported
if 'core' not in sys.modules:
    sys.modules['core'] = _current_module
    sys.modules['core.cli'] = sys.modules.get('usf_fabric_cli.cli')
    sys.modules['core.exceptions'] = sys.modules.get('usf_fabric_cli.exceptions')

__all__ = [
    "app",
    "FabricDeployer", 
    "FabricCLIError",
    "FabricCLINotFoundError",
    "__version__",
]
