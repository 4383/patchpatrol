"""
Gemini API backend for AI inference.

This module implements the Gemini backend using Google's Generative AI API
for cloud-based model execution.
"""

import logging
import os
from typing import Any, Optional

from .base import BaseBackend, InferenceError, ModelLoadError

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class GeminiBackend(BaseBackend):
    """
    Gemini API backend for text generation.

    Uses Google's Generative AI API for cloud-based inference.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cloud",
        temperature: float = 0.2,
        max_new_tokens: int = 512,
        top_p: float = 0.9,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Gemini backend.

        Args:
            model_path: Gemini model name (e.g., 'gemini-pro', 'gemini-pro-vision')
            device: Always "cloud" for API-based models
            temperature: Sampling temperature
            max_new_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            **kwargs: Additional parameters
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "Gemini backend requires 'google-generativeai'. "
                "Install with: pip install patchpatrol[gemini]"
            )

        # For API models, model_path is actually the model name
        super().__init__(model_path, "cloud", temperature, max_new_tokens, top_p, **kwargs)

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_name = model_path
        self.validate_parameters()

    def load_model(self) -> None:
        """
        Initialize the Gemini API client.

        Raises:
            ModelLoadError: If API initialization fails
        """
        try:
            # Configure the API key
            genai.configure(api_key=self.api_key)

            # Test the connection by listing models
            available_models = list(genai.list_models())
            model_names = [model.name for model in available_models]

            # Check if our requested model is available
            full_model_name = f"models/{self.model_name}"
            if full_model_name not in model_names:
                logger.warning(f"Model '{self.model_name}' not found in available models")
                logger.debug(f"Available models: {model_names}")

            # Initialize the model
            self._model = genai.GenerativeModel(self.model_name)
            self._is_loaded = True

            logger.info(f"Successfully initialized Gemini model: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            raise ModelLoadError(f"Failed to initialize Gemini API: {e}") from e

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate text using the Gemini API.

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
            # Combine system and user prompts
            # Gemini doesn't have explicit system/user roles like OpenAI
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                max_output_tokens=self.max_new_tokens,
                stop_sequences=None,
            )

            # Configure safety settings to be permissive for code review
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            # Generate response
            response = self._model.generate_content(  # type: ignore[attr-defined]
                full_prompt, generation_config=generation_config, safety_settings=safety_settings
            )

            # Check if the response was blocked
            if response.prompt_feedback.block_reason:
                raise InferenceError(
                    f"Gemini blocked the request: {response.prompt_feedback.block_reason}"
                )

            # Extract the text
            if response.parts:
                content = response.text.strip()
                logger.debug(f"Generated response length: {len(content)} characters")
                return content  # type: ignore[no-any-return]
            else:
                raise InferenceError("Gemini returned empty response")

        except Exception as e:
            logger.error(f"Gemini inference failed: {e}")
            raise InferenceError(f"Gemini inference failed: {e}") from e

    def unload_model(self) -> None:
        """Unload the model (no-op for API models)."""
        self._model = None
        self._is_loaded = False
        logger.info("Gemini model connection closed")

    def get_info(self) -> dict[str, Any]:
        """Get detailed information about the Gemini backend."""
        info = super().get_info()
        info.update(
            {
                "model_name": self.model_name,
                "api_key_set": bool(self.api_key),
                "gemini_available": GEMINI_AVAILABLE,
            }
        )
        return info

    def validate_parameters(self) -> None:
        """Validate Gemini-specific parameters."""
        # Skip base class validation for device (API models don't use local devices)
        # Only validate core parameters
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(f"Temperature must be between 0.0 and 1.0, got {self.temperature}")

        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError(f"top_p must be between 0.0 and 1.0, got {self.top_p}")

        if self.max_new_tokens <= 0:
            raise ValueError(f"max_new_tokens must be positive, got {self.max_new_tokens}")

        # Gemini-specific validations
        if self.max_new_tokens > 8192:
            logger.warning(
                f"max_new_tokens ({self.max_new_tokens}) is quite large. "
                "Consider reducing for cost efficiency."
            )

        # Validate model name format
        valid_prefixes = [
            "gemini-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-exp",
        ]
        if not any(self.model_name.startswith(prefix) for prefix in valid_prefixes):
            logger.warning(
                f"Model name '{self.model_name}' may not be valid. "
                f"Expected names starting with: {valid_prefixes}"
            )


# Convenience function for testing API connectivity
def test_gemini_connection(api_key: Optional[str] = None) -> bool:
    """
    Test Gemini API connectivity.

    Args:
        api_key: API key to test (uses env var if not provided)

    Returns:
        True if connection successful, False otherwise
    """
    try:
        test_key = api_key or os.getenv("GEMINI_API_KEY")
        if not test_key:
            return False

        genai.configure(api_key=test_key)
        list(genai.list_models())
        return True

    except Exception as e:
        logger.debug(f"Gemini connection test failed: {e}")
        return False
