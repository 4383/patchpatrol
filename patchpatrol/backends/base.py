"""
Base backend interface for AI inference engines.

This module defines the common interface that all backend implementations
must follow for consistent behavior across ONNX and llama.cpp engines.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BackendError(Exception):
    """Base exception for backend-related errors."""

    pass


class ModelLoadError(BackendError):
    """Raised when model loading fails."""

    pass


class InferenceError(BackendError):
    """Raised when inference fails."""

    pass


class BaseBackend(ABC):
    """
    Abstract base class for AI inference backends.

    All backend implementations must inherit from this class and implement
    the required methods for model loading and text generation.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        temperature: float = 0.2,
        max_new_tokens: int = 512,
        top_p: float = 0.9,
        **kwargs,
    ):
        """
        Initialize the backend with common parameters.

        Args:
            model_path: Path to the model file or directory
            device: Compute device ("cpu" or "cuda")
            temperature: Sampling temperature (0.0-1.0)
            max_new_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            **kwargs: Backend-specific additional parameters
        """
        self.model_path = model_path
        self.device = device
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.top_p = top_p
        self.extra_params = kwargs
        self._model = None
        self._tokenizer = None
        self._is_loaded = False

    @abstractmethod
    def load_model(self) -> None:
        """
        Load the model and tokenizer.

        Raises:
            ModelLoadError: If model loading fails
        """
        pass

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a response given system and user prompts.

        Args:
            system_prompt: The system prompt defining the task
            user_prompt: The user prompt with specific content to analyze

        Returns:
            Raw model response as string (should contain JSON)

        Raises:
            InferenceError: If generation fails
            ModelLoadError: If model is not loaded
        """
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """
        Unload the model to free memory.
        """
        pass

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._is_loaded

    def get_info(self) -> dict[str, Any]:
        """
        Get information about the backend and model.

        Returns:
            Dictionary with backend information
        """
        return {
            "backend_type": self.__class__.__name__,
            "model_path": self.model_path,
            "device": self.device,
            "temperature": self.temperature,
            "max_new_tokens": self.max_new_tokens,
            "top_p": self.top_p,
            "is_loaded": self.is_loaded(),
        }

    def validate_parameters(self) -> None:
        """
        Validate backend parameters.

        Raises:
            ValueError: If parameters are invalid
        """
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(f"Temperature must be between 0.0 and 1.0, got {self.temperature}")

        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(f"top_p must be between 0.0 and 1.0, got {self.top_p}")

        if self.max_new_tokens <= 0:
            raise ValueError(f"max_new_tokens must be positive, got {self.max_new_tokens}")

        if self.device not in ["cpu", "cuda"]:
            logger.warning(f"Unusual device '{self.device}', expected 'cpu' or 'cuda'")

    def __enter__(self):
        """Context manager entry."""
        if not self.is_loaded():
            self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.is_loaded():
            self.unload_model()


def get_backend(backend_type: str, **kwargs) -> BaseBackend:
    """
    Factory function to create backend instances.

    Args:
        backend_type: Type of backend ("onnx", "llama", or "gemini")
        **kwargs: Parameters to pass to backend constructor

    Returns:
        Backend instance

    Raises:
        ValueError: If backend_type is not supported
        ImportError: If required dependencies are not installed
    """
    backend_type = backend_type.lower()

    if backend_type == "onnx":
        try:
            from .onnx_backend import ONNXBackend

            return ONNXBackend(**kwargs)
        except ImportError as e:
            raise ImportError(
                "ONNX backend requires 'optimum[onnxruntime]' and 'transformers'. "
                "Install with: pip install patchpatrol[onnx]"
            ) from e

    elif backend_type == "llama":
        try:
            from .llama_backend import LlamaBackend

            return LlamaBackend(**kwargs)
        except ImportError as e:
            raise ImportError(
                "Llama backend requires 'llama-cpp-python'. "
                "Install with: pip install patchpatrol[llama]"
            ) from e

    elif backend_type == "gemini":
        try:
            from .gemini_backend import GeminiBackend

            return GeminiBackend(**kwargs)
        except ImportError as e:
            raise ImportError(
                "Gemini backend requires 'google-generativeai'. "
                "Install with: pip install patchpatrol[gemini]"
            ) from e

    else:
        raise ValueError(
            f"Unsupported backend type: {backend_type}. "
            "Supported types: 'onnx', 'llama', 'gemini'"
        )
