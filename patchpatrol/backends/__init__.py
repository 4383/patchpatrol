"""
Backend implementations for AI inference.

Supports ONNX Runtime, llama.cpp, and Gemini backends for local and cloud model execution.
"""

from .base import BaseBackend

__all__ = ["BaseBackend"]
