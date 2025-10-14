"""
ONNX Runtime backend for AI inference.

This module implements the ONNX backend using optimum and transformers
for local model execution with CPU or CUDA providers.
"""
# mypy: disable-error-code=unreachable

import logging
from pathlib import Path
from typing import Any, Optional

from .base import BaseBackend, InferenceError, ModelLoadError

logger = logging.getLogger(__name__)

try:
    import torch
    from optimum.onnxruntime import ORTModelForCausalLM
    from transformers import AutoConfig, AutoTokenizer

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ORTModelForCausalLM = None
    AutoTokenizer = None
    AutoConfig = None
    torch = None


class ONNXBackend(BaseBackend):
    """
    ONNX Runtime backend for text generation.

    Uses Optimum ONNX Runtime integration with Transformers for
    efficient local inference on CPU or CUDA devices.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        temperature: float = 0.2,
        max_new_tokens: int = 512,
        top_p: float = 0.9,
        provider: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize ONNX backend.

        Args:
            model_path: Path to ONNX model directory
            device: Device for computation ("cpu" or "cuda")
            temperature: Sampling temperature
            max_new_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            provider: ONNX execution provider (auto-detected if None)
            **kwargs: Additional parameters
        """
        if not ONNX_AVAILABLE:
            raise ImportError(
                "ONNX backend requires 'optimum[onnxruntime]' and 'transformers'. "
                "Install with: pip install patchpatrol[onnx]"
            )

        super().__init__(model_path, device, temperature, max_new_tokens, top_p, **kwargs)
        self.provider = provider or self._get_provider()
        self.validate_parameters()

    def _get_provider(self) -> str:
        """Determine the appropriate ONNX execution provider."""
        if self.device == "cuda" and torch and torch.cuda.is_available():
            return "CUDAExecutionProvider"
        return "CPUExecutionProvider"

    def _validate_model_path(self) -> None:
        """Validate that the model path exists and contains required files."""
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise ModelLoadError(f"Model path does not exist: {self.model_path}")

        if not model_path.is_dir():
            raise ModelLoadError(f"Model path must be a directory: {self.model_path}")

        # Check for required files
        required_files = ["config.json"]
        missing_files = []
        for file in required_files:
            if not (model_path / file).exists():
                missing_files.append(file)

        if missing_files:
            raise ModelLoadError(f"Missing required files in {self.model_path}: {missing_files}")

    def load_model(self) -> None:
        """
        Load the ONNX model and tokenizer.

        Raises:
            ModelLoadError: If model loading fails
        """
        try:
            self._validate_model_path()
            logger.info(f"Loading ONNX model from {self.model_path}")

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=False,  # Security: don't execute remote code
            )

            # Ensure tokenizer has proper padding
            if self._tokenizer.pad_token is None:  # type: ignore[attr-defined]
                self._tokenizer.pad_token = self._tokenizer.eos_token  # type: ignore[attr-defined]

            # Load ONNX model
            providers = [self.provider]
            self._model = ORTModelForCausalLM.from_pretrained(
                self.model_path,
                providers=providers,
                trust_remote_code=False,  # Security: don't execute remote code
            )

            self._is_loaded = True
            logger.info(f"Successfully loaded ONNX model with provider: {self.provider}")

        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise ModelLoadError(f"Failed to load ONNX model: {e}") from e

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate text using the loaded ONNX model.

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
            # Format the conversation
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Apply chat template if available
            if hasattr(self._tokenizer, "apply_chat_template"):
                prompt = self._tokenizer.apply_chat_template(  # type: ignore[attr-defined]
                    messages, tokenize=False, add_generation_prompt=True
                )
            else:
                # Fallback to simple concatenation
                prompt = f"System: {system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"

            # Tokenize input
            inputs = self._tokenizer(  # type: ignore[misc]
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=4096,  # Reasonable context limit
                padding=True,
            )

            # Generate response
            with torch.no_grad():
                outputs = self._model.generate(  # type: ignore[attr-defined]
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    do_sample=True if self.temperature > 0 else False,
                    pad_token_id=self._tokenizer.pad_token_id,  # type: ignore[attr-defined]
                    eos_token_id=self._tokenizer.eos_token_id,  # type: ignore[attr-defined]
                    repetition_penalty=1.1,
                    length_penalty=1.0,
                )

            # Decode response
            input_length = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_length:]
            response = self._tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()  # type: ignore[attr-defined]

            logger.debug(f"Generated response length: {len(response)} characters")
            return response  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            raise InferenceError(f"ONNX inference failed: {e}") from e

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None

        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None

        self._is_loaded = False

        # Force garbage collection if torch is available
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("ONNX model unloaded")

    def get_info(self) -> dict[str, Any]:
        """Get detailed information about the ONNX backend."""
        info = super().get_info()
        info.update(
            {
                "provider": self.provider,
                "onnx_available": ONNX_AVAILABLE,
            }
        )

        if self.is_loaded() and self._model:
            try:
                config = AutoConfig.from_pretrained(self.model_path)
                info.update(
                    {
                        "model_type": config.model_type,
                        "vocab_size": getattr(config, "vocab_size", "unknown"),
                        "hidden_size": getattr(config, "hidden_size", "unknown"),
                    }
                )
            except Exception:
                pass  # Config info is optional

        return info
