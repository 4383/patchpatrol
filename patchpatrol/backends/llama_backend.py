"""
llama.cpp backend for AI inference.

This module implements the llama.cpp backend using llama-cpp-python
for local GGUF model execution.
"""
# mypy: disable-error-code=unreachable

import logging
from pathlib import Path
from typing import Any, Optional

from .base import BaseBackend, InferenceError, ModelLoadError

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama

    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    Llama = None


class LlamaBackend(BaseBackend):
    """
    llama.cpp backend for text generation.

    Uses llama-cpp-python for efficient inference with quantized GGUF models.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        temperature: float = 0.2,
        max_new_tokens: int = 512,
        top_p: float = 0.9,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        n_threads: Optional[int] = None,
        **kwargs,
    ):
        """
        Initialize llama.cpp backend.

        Args:
            model_path: Path to GGUF model file
            device: Device for computation ("cpu" or "cuda")
            temperature: Sampling temperature
            max_new_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            n_ctx: Context length
            n_gpu_layers: Number of layers to offload to GPU
            n_threads: Number of CPU threads (auto-detect if None)
            **kwargs: Additional llama.cpp parameters
        """
        if not LLAMA_AVAILABLE:
            raise ImportError(
                "Llama backend requires 'llama-cpp-python'. "
                "Install with: pip install patchpatrol[llama]"
            )

        super().__init__(model_path, device, temperature, max_new_tokens, top_p, **kwargs)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers if device == "cuda" else 0
        self.n_threads = n_threads
        self.validate_parameters()

    def _validate_model_path(self) -> None:
        """Validate that the model file exists and has correct extension."""
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ModelLoadError(f"Model file does not exist: {self.model_path}")

        if not model_path.is_file():
            raise ModelLoadError(f"Model path must be a file: {self.model_path}")

        if model_path.suffix.lower() not in [".gguf", ".ggml"]:
            logger.warning(
                f"Model file {self.model_path} does not have .gguf extension. "
                "This may not be a valid llama.cpp model."
            )

    def load_model(self) -> None:
        """
        Load the GGUF model.

        Raises:
            ModelLoadError: If model loading fails
        """
        try:
            self._validate_model_path()
            logger.info(f"Loading llama.cpp model from {self.model_path}")

            # Prepare llama.cpp parameters
            llama_params = {
                "model_path": self.model_path,
                "n_ctx": self.n_ctx,
                "n_gpu_layers": self.n_gpu_layers,
                "verbose": False,  # Reduce llama.cpp logging
                "use_mmap": True,  # Memory-mapped file loading
                "use_mlock": False,  # Don't lock memory
            }

            # Set thread count
            if self.n_threads is not None:
                llama_params["n_threads"] = self.n_threads

            # Add any extra parameters
            llama_params.update(self.extra_params)

            # Load model
            self._model = Llama(**llama_params)
            self._is_loaded = True

            logger.info(
                f"Successfully loaded llama.cpp model "
                f"(ctx: {self.n_ctx}, gpu_layers: {self.n_gpu_layers})"
            )

        except Exception as e:
            logger.error(f"Failed to load llama.cpp model: {e}")
            raise ModelLoadError(f"Failed to load llama.cpp model: {e}") from e

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate text using the loaded llama.cpp model.

        Args:
            system_prompt: System prompt defining the task
            user_prompt: User prompt with content to analyze

        Returns:
            Generated text response

        Raises:
            ModelLoadError: If model is not loaded
            InferenceError: If generation fails
        """
        if not self.is_loaded():
            raise ModelLoadError("Model not loaded. Call load_model() first.")

        try:
            # Format as chat messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Use chat completion interface
            response = self._model.create_chat_completion(  # type: ignore[attr-defined]
                messages=messages,
                max_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                frequency_penalty=0.1,  # Reduce repetition
                presence_penalty=0.1,  # Encourage diversity
                stop=None,  # Let model decide when to stop
                stream=False,
            )

            # Extract the response content
            if (
                response
                and "choices" in response
                and len(response["choices"]) > 0
                and "message" in response["choices"][0]
                and "content" in response["choices"][0]["message"]
            ):
                content = response["choices"][0]["message"]["content"].strip()
                logger.debug(f"Generated response length: {len(content)} characters")
                return content  # type: ignore[no-any-return]
            else:
                raise InferenceError("Invalid response format from llama.cpp")

        except Exception as e:
            logger.error(f"llama.cpp inference failed: {e}")
            raise InferenceError(f"llama.cpp inference failed: {e}") from e

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            # llama.cpp models don't have explicit cleanup
            # but we can delete the reference
            del self._model
            self._model = None

        self._is_loaded = False
        logger.info("llama.cpp model unloaded")

    def get_info(self) -> dict[str, Any]:
        """Get detailed information about the llama.cpp backend."""
        info = super().get_info()
        info.update(
            {
                "n_ctx": self.n_ctx,
                "n_gpu_layers": self.n_gpu_layers,
                "n_threads": self.n_threads,
                "llama_available": LLAMA_AVAILABLE,
            }
        )

        if self.is_loaded() and self._model:
            # Get model metadata if available
            try:
                # llama.cpp models may have metadata
                if hasattr(self._model, "metadata"):
                    metadata = self._model.metadata
                    info.update(
                        {
                            "model_metadata": metadata,
                        }
                    )
            except Exception:
                pass  # Metadata is optional

        return info

    def validate_parameters(self) -> None:
        """Validate llama.cpp specific parameters."""
        super().validate_parameters()

        if self.n_ctx <= 0:
            raise ValueError(f"n_ctx must be positive, got {self.n_ctx}")

        if self.n_gpu_layers < 0:
            raise ValueError(f"n_gpu_layers must be non-negative, got {self.n_gpu_layers}")

        if self.n_threads is not None and self.n_threads <= 0:
            raise ValueError(f"n_threads must be positive, got {self.n_threads}")

        # Warn about large context sizes
        if self.n_ctx > 8192:
            logger.warning(
                f"Large context size ({self.n_ctx}) may impact performance. "
                "Consider reducing n_ctx for faster inference."
            )

        # Warn about GPU layers on CPU
        if self.device == "cpu" and self.n_gpu_layers > 0:
            logger.warning(
                f"n_gpu_layers={self.n_gpu_layers} specified but device is 'cpu'. "
                "GPU layers will be ignored."
            )
