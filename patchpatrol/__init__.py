"""
PatchPatrol - AI-powered commit review system for pre-commit hooks.

A local, offline AI system that analyzes Git commits for code quality,
coherence, and commit message clarity using ONNX or llama.cpp backends.
"""

__version__ = "0.1.0"
__author__ = "PatchPatrol Team"
__email__ = "dev@patchpatrol.dev"

from .cli import main
from .models import download_model, get_model_manager, list_models

__all__ = ["main", "get_model_manager", "list_models", "download_model"]
