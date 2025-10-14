"""
Backend implementations for AI inference.

Supports ONNX Runtime and llama.cpp backends for local model execution.
"""

from .base import BaseBackend

__all__ = ["BaseBackend"]
