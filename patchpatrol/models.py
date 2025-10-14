"""
Model registry and downloading functionality.

This module provides automatic model downloading, caching, and management
for PatchPatrol, making it truly standalone for CI/CD environments.
"""

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a downloadable or API-based model."""

    name: str
    backend: str  # "onnx", "llama", or "gemini"
    url: Optional[str]  # None for API models
    size_mb: int
    description: str
    sha256: Optional[str] = None
    filename: Optional[str] = None
    requirements: Optional[list[str]] = None
    is_api: bool = False  # True for API-based models

    def __post_init__(self):
        """Auto-generate filename from URL if not provided."""
        if self.filename is None and self.url:
            self.filename = os.path.basename(urlparse(self.url).path)
        elif self.is_api and self.filename is None:
            # For API models, filename is just the model name
            self.filename = self.name


# Model registry - curated list of tested models
MODEL_REGISTRY: dict[str, ModelInfo] = {
    # Lightweight models for CI/CD
    "granite-3b-code": ModelInfo(
        name="granite-3b-code",
        backend="llama",
        url="https://huggingface.co/ibm-granite/granite-3b-code-instruct-GGUF/resolve/main/granite-3b-code-instruct.Q4_K_M.gguf",
        size_mb=1800,
        description="IBM Granite 3B - Fast, lightweight code model perfect for CI/CD",
        sha256=None,  # Would be real hash in production
        requirements=["llama"],
    ),
    "granite-8b-code": ModelInfo(
        name="granite-8b-code",
        backend="llama",
        url="https://huggingface.co/ibm-granite/granite-8b-code-instruct-GGUF/resolve/main/granite-8b-code-instruct.Q4_K_M.gguf",
        size_mb=4500,
        description="IBM Granite 8B - Balanced quality and performance",
        sha256=None,
        requirements=["llama"],
    ),
    "codellama-7b": ModelInfo(
        name="codellama-7b",
        backend="llama",
        url="https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.q4_k_m.gguf",
        size_mb=4100,
        description="Meta CodeLlama 7B - Excellent for code review",
        sha256=None,
        requirements=["llama"],
    ),
    "codegemma-2b": ModelInfo(
        name="codegemma-2b",
        backend="llama",
        url="https://huggingface.co/google/codegemma-2b-it-GGUF/resolve/main/codegemma-2b-it.q4_k_m.gguf",
        size_mb=1600,
        description="Google CodeGemma 2B - Ultra-fast for quick reviews",
        sha256=None,
        requirements=["llama"],
    ),
    # ONNX models (smaller examples)
    "distilgpt2-onnx": ModelInfo(
        name="distilgpt2-onnx",
        backend="onnx",
        url="https://huggingface.co/optimum/distilgpt2/resolve/main/model.onnx",
        size_mb=350,
        description="DistilGPT2 ONNX - Lightweight for basic reviews",
        sha256=None,
        requirements=["onnx"],
    ),
    # Gemini API models - Latest working series (2.0)
    "gemini-2.0-flash-exp": ModelInfo(
        name="gemini-2.0-flash-exp",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 2.0 Flash Experimental - Latest experimental model with advanced capabilities",
        is_api=True,
        requirements=["gemini"],
    ),
    "gemini-2.0-flash": ModelInfo(
        name="gemini-2.0-flash",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 2.0 Flash - Stable fast model with enhanced performance",
        is_api=True,
        requirements=["gemini"],
    ),
    # Future Gemini models (listed but access restricted)
    "gemini-2.5-pro": ModelInfo(
        name="gemini-2.5-pro",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 2.5 Pro - Future high-capability model (requires special access)",
        is_api=True,
        requirements=["gemini"],
    ),
    "gemini-2.5-flash": ModelInfo(
        name="gemini-2.5-flash",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 2.5 Flash - Future fast model (requires special access)",
        is_api=True,
        requirements=["gemini"],
    ),
    "gemini-1.5-pro": ModelInfo(
        name="gemini-1.5-pro",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 1.5 Pro - Legacy stable model",
        is_api=True,
        requirements=["gemini"],
    ),
    "gemini-1.5-flash": ModelInfo(
        name="gemini-1.5-flash",
        backend="gemini",
        url=None,  # API model
        size_mb=0,  # No local storage
        description="Google Gemini 1.5 Flash - Legacy fast model",
        is_api=True,
        requirements=["gemini"],
    ),
}

# Default models for different use cases
DEFAULT_MODELS = {
    "ci": "granite-3b-code",  # Fast for CI/CD
    "dev": "granite-3b-code",  # Good for development
    "quality": "codellama-7b",  # Best quality
    "minimal": "codegemma-2b",  # Smallest/fastest
    "cloud": "gemini-2.0-flash",  # Fast cloud-based option with latest working AI
    "premium": "gemini-2.0-flash-exp",  # Premium cloud with experimental features
}


class ModelManager:
    """Manages model downloading, caching, and validation."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize model manager.

        Args:
            cache_dir: Directory to cache models (defaults to user cache)
        """
        if cache_dir is None:
            cache_dir = self._get_default_cache_dir()

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.cache_dir / "registry.json"

        logger.debug(f"Model cache directory: {self.cache_dir}")

    def _get_default_cache_dir(self) -> str:
        """Get default cache directory based on OS."""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
            return os.path.join(base, "PatchPatrol", "models")
        else:  # Unix-like
            base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
            return os.path.join(base, "patchpatrol", "models")

    def list_available_models(self) -> dict[str, ModelInfo]:
        """Get list of all available models."""
        return MODEL_REGISTRY.copy()

    def list_cached_models(self) -> list[str]:
        """Get list of locally cached models."""
        cached = []
        for model_name in MODEL_REGISTRY.keys():
            if self.is_model_cached(model_name):
                cached.append(model_name)
        return cached

    def is_model_cached(self, model_name: str) -> bool:
        """Check if model is already cached locally."""
        if model_name not in MODEL_REGISTRY:
            return False

        model_info = MODEL_REGISTRY[model_name]

        # API models are always "cached" (no local files needed)
        if model_info.is_api:
            return True

        model_path = self.cache_dir / model_name / model_info.filename
        return model_path.exists()

    def get_model_path(self, model_name: str) -> str:
        """
        Get local path to model, downloading if necessary.

        Args:
            model_name: Name of the model or alias

        Returns:
            Local path to the model or model name for API models

        Raises:
            ValueError: If model name is not found
            RuntimeError: If download fails
        """
        # Handle aliases
        if model_name in DEFAULT_MODELS:
            model_name = DEFAULT_MODELS[model_name]

        if model_name not in MODEL_REGISTRY:
            available = list(MODEL_REGISTRY.keys()) + list(DEFAULT_MODELS.keys())
            raise ValueError(f"Unknown model '{model_name}'. Available: {available}")

        model_info = MODEL_REGISTRY[model_name]

        # For API models, return the model name directly
        if model_info.is_api:
            return model_name

        model_dir = self.cache_dir / model_name
        model_path = model_dir / model_info.filename

        # Download if not cached
        if not self.is_model_cached(model_name):
            logger.info(f"Model '{model_name}' not cached, downloading...")
            self.download_model(model_name)

        # For ONNX models, return the directory; for llama models, return the file
        if model_info.backend == "onnx":
            return str(model_dir)
        else:
            return str(model_path)

    def download_model(self, model_name: str, force: bool = False) -> str:
        """
        Download a model to the cache.

        Args:
            model_name: Name of the model to download
            force: Force re-download even if cached

        Returns:
            Local path to the downloaded model or model name for API models

        Raises:
            ValueError: If model name is not found
            RuntimeError: If download fails
        """
        if model_name not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model: {model_name}")

        model_info = MODEL_REGISTRY[model_name]

        # API models don't need downloading
        if model_info.is_api:
            logger.info(f"API model '{model_name}' ready to use")
            return model_name

        model_dir = self.cache_dir / model_name
        model_path = model_dir / model_info.filename

        # Skip if already cached and not forcing
        if not force and self.is_model_cached(model_name):
            logger.info(f"Model '{model_name}' already cached")
            return str(model_path)

        # Create model directory
        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading {model_name} ({model_info.size_mb}MB) from {model_info.url}")

        try:
            # Use subprocess to download with progress
            self._download_with_progress(model_info.url, str(model_path))

            # Validate download
            if model_info.sha256:
                if not self._validate_file_hash(str(model_path), model_info.sha256):
                    os.remove(model_path)
                    raise RuntimeError(f"Hash validation failed for {model_name}")

            # For ONNX models, we might need to download additional files
            if model_info.backend == "onnx":
                self._download_onnx_files(model_info, model_dir)

            logger.info(f"Successfully downloaded {model_name}")
            return str(model_path)

        except Exception as e:
            # Cleanup on failure
            if model_path.exists():
                os.remove(model_path)
            raise RuntimeError(f"Failed to download {model_name}: {e}") from e

    def _download_with_progress(self, url: str, output_path: str) -> None:
        """Download file with progress indicator."""
        try:
            # Try using wget first (shows progress)
            result = subprocess.run(
                ["wget", "--progress=bar", "--show-progress", "-O", output_path, url],
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, "wget")

        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to curl
            try:
                result = subprocess.run(
                    ["curl", "-L", "--progress-bar", "-o", output_path, url],
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )

                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, "curl")

            except (subprocess.CalledProcessError, FileNotFoundError):
                # Final fallback to Python urllib
                import urllib.request

                urllib.request.urlretrieve(url, output_path)

    def _validate_file_hash(self, file_path: str, expected_hash: str) -> bool:
        """Validate file SHA256 hash."""
        if not expected_hash:
            return True

        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest() == expected_hash

    def _download_onnx_files(self, model_info: ModelInfo, model_dir: Path) -> None:
        """Download additional files needed for ONNX models."""
        # For ONNX models, we typically need config.json and tokenizer files
        base_url = model_info.url.rsplit("/", 1)[0]

        additional_files = ["config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt"]

        for filename in additional_files:
            file_url = f"{base_url}/{filename}"
            file_path = model_dir / filename

            try:
                self._download_with_progress(file_url, str(file_path))
                logger.debug(f"Downloaded {filename}")
            except Exception as e:
                logger.debug(f"Could not download {filename}: {e}")
                # Some files are optional
                continue

    def remove_model(self, model_name: str) -> bool:
        """
        Remove a cached model.

        Args:
            model_name: Name of the model to remove

        Returns:
            True if model was removed, False if not cached or is API model
        """
        if model_name not in MODEL_REGISTRY:
            return False

        model_info = MODEL_REGISTRY[model_name]

        # Can't remove API models (they're not stored locally)
        if model_info.is_api:
            logger.info(f"Cannot remove API model: {model_name}")
            return False

        if not self.is_model_cached(model_name):
            return False

        model_dir = self.cache_dir / model_name

        try:
            import shutil

            shutil.rmtree(model_dir)
            logger.info(f"Removed cached model: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove model {model_name}: {e}")
            return False

    def clean_cache(self, keep_models: Optional[list[str]] = None) -> int:
        """
        Clean the model cache.

        Args:
            keep_models: List of models to keep (remove all others)

        Returns:
            Number of models removed
        """
        if keep_models is None:
            keep_models = []

        removed_count = 0
        for model_name in self.list_cached_models():
            if model_name not in keep_models:
                if self.remove_model(model_name):
                    removed_count += 1

        return removed_count

    def get_cache_size(self) -> int:
        """Get total size of model cache in bytes."""
        total_size = 0

        for root, _dirs, files in os.walk(self.cache_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)

        return total_size


# Global model manager instance
_model_manager = None


def get_model_manager() -> ModelManager:
    """Get global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def get_model_path(model_name: str) -> str:
    """Convenience function to get model path."""
    return get_model_manager().get_model_path(model_name)


def list_models() -> dict[str, ModelInfo]:
    """Convenience function to list available models."""
    return get_model_manager().list_available_models()


def download_model(model_name: str, force: bool = False) -> str:
    """Convenience function to download a model."""
    return get_model_manager().download_model(model_name, force)
