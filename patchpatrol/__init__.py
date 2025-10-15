"""
PatchPatrol - AI-powered commit review system for pre-commit hooks.

A local, offline AI system that analyzes Git commits for code quality,
coherence, and commit message clarity using ONNX backends.
"""

try:
    from ._version import __version__
except ImportError:
    # Fallback for development installs without hatch
    __version__ = "dev"
__author__ = "PatchPatrol Team"
__email__ = "dev@patchpatrol.dev"

from .cli import main
from .models import download_model, get_model_manager, list_models

__all__ = ["main", "get_model_manager", "list_models", "download_model"]
