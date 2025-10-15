"""Unit tests for backend base classes and utilities."""

from unittest.mock import Mock, patch

import pytest

from patchpatrol.backends.base import (
    BackendError,
    BaseBackend,
    get_backend,
)


class TestBackendError:
    """Test BackendError exception."""

    def test_backend_error_inheritance(self):
        """Test that BackendError inherits from Exception."""
        error = BackendError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"


class TestBaseBackend:
    """Test BaseBackend base class."""

    def test_base_backend_is_abstract(self):
        """Test that BaseBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseBackend("test_model")  # type: ignore[abstract]

    def test_concrete_backend_implementation(self):
        """Test implementing BaseBackend abstract methods."""

        class TestBackend(BaseBackend):
            def load_model(self):
                self._is_loaded = True

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                return '{"score": 0.8, "verdict": "approve", "comments": ["test"]}'

            def unload_model(self):
                self._is_loaded = False

        backend = TestBackend("test_model", device="cpu")

        assert backend.model_path == "test_model"
        assert backend.device == "cpu"
        assert backend.is_loaded() is False

        backend.load_model()
        assert backend.is_loaded() is True

        result = backend.generate_json("system", "user")
        assert "score" in result

        backend.unload_model()
        assert backend.is_loaded() is False

    def test_backend_info(self):
        """Test get_info method."""

        class TestBackend(BaseBackend):
            def load_model(self):
                pass

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                return "{}"

            def unload_model(self):
                pass

        backend = TestBackend("test_model", device="cuda", temperature=0.5)
        info = backend.get_info()

        assert info["model_path"] == "test_model"
        assert info["device"] == "cuda"
        assert info["temperature"] == 0.5
        assert info["is_loaded"] is False
        assert "backend_type" in info

    def test_backend_context_manager(self):
        """Test backend as context manager."""

        class TestBackend(BaseBackend):
            def load_model(self):
                self._is_loaded = True

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                if not self.is_loaded():
                    raise BackendError("Model not loaded")
                return "{}"

            def unload_model(self):
                self._is_loaded = False

        backend = TestBackend("test_model")

        assert backend.is_loaded() is False

        with backend:
            assert backend.is_loaded() is True
            result = backend.generate_json("system", "user")
            assert result == "{}"

        assert backend.is_loaded() is False

    def test_backend_context_manager_exception(self):
        """Test backend context manager handles exceptions."""

        class TestBackend(BaseBackend):
            def load_model(self):
                self._is_loaded = True

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                raise Exception("Test error")

            def unload_model(self):
                self._is_loaded = False

        backend = TestBackend("test_model")

        with pytest.raises(Exception, match="Test error"):
            with backend:
                backend.generate_json("system", "user")

        # Should still unload even after exception
        assert backend.is_loaded() is False


class TestGetBackend:
    """Test get_backend factory function."""

    @patch("patchpatrol.backends.onnx_backend.ONNXBackend")
    def test_get_onnx_backend(self, mock_onnx_class):
        """Test creating ONNX backend."""
        mock_backend = Mock()
        mock_onnx_class.return_value = mock_backend

        backend = get_backend("onnx", model_path="test_model", device="cpu")

        mock_onnx_class.assert_called_once_with(model_path="test_model", device="cpu")
        assert backend == mock_backend

    @patch("patchpatrol.backends.gemini_backend.GeminiBackend")
    def test_get_gemini_backend(self, mock_gemini_class):
        """Test creating Gemini backend."""
        mock_backend = Mock()
        mock_gemini_class.return_value = mock_backend

        backend = get_backend("gemini", model_path="gemini-2.0-flash", temperature=0.1)

        mock_gemini_class.assert_called_once_with(model_path="gemini-2.0-flash", temperature=0.1)
        assert backend == mock_backend

    def test_get_backend_unknown_type(self):
        """Test error for unknown backend type."""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            get_backend("unknown", model_path="test_model")

    @patch(
        "patchpatrol.backends.onnx_backend.ONNXBackend", side_effect=ImportError("Module not found")
    )
    def test_get_onnx_backend_not_available(self, mock_import):
        """Test error when ONNX backend not available."""
        with pytest.raises(ImportError, match="ONNX backend requires"):
            get_backend("onnx", model_path="test_model")

    @patch(
        "patchpatrol.backends.gemini_backend.GeminiBackend",
        side_effect=ImportError("Module not found"),
    )
    def test_get_gemini_backend_not_available(self, mock_import):
        """Test error when Gemini backend not available."""
        with pytest.raises(ImportError, match="Gemini backend requires"):
            get_backend("gemini", model_path="test_model")

    @patch("patchpatrol.backends.onnx_backend.ONNXBackend")
    def test_get_backend_with_custom_params(self, mock_onnx_class):
        """Test creating backend with custom parameters."""
        mock_backend = Mock()
        mock_onnx_class.return_value = mock_backend

        get_backend(
            "onnx",
            model_path="test_model",
            device="cuda",
            temperature=0.5,
            max_new_tokens=1024,
            top_p=0.8,
        )

        mock_onnx_class.assert_called_once_with(
            model_path="test_model", device="cuda", temperature=0.5, max_new_tokens=1024, top_p=0.8
        )

    @patch("patchpatrol.backends.onnx_backend.ONNXBackend")
    def test_get_backend_import_error(self, mock_onnx_class):
        """Test handling import errors."""
        mock_onnx_class.side_effect = ImportError("Module not found")

        with pytest.raises(ImportError, match="ONNX backend requires"):
            get_backend("onnx", model_path="test_model")


class TestBackendAvailability:
    """Test backend availability detection."""

    def test_backend_imports(self):
        """Test that base backend functions can be imported."""
        from patchpatrol.backends.base import BackendError, BaseBackend, get_backend

        assert BaseBackend is not None
        assert BackendError is not None
        assert get_backend is not None

    @patch("patchpatrol.backends.onnx_backend.ONNXBackend")
    def test_onnx_backend_creation(self, mock_class):
        """Test ONNX backend can be created when available."""
        mock_class.return_value = Mock()
        backend = get_backend("onnx", model_path="test")
        assert backend is not None

    @patch("patchpatrol.backends.gemini_backend.GeminiBackend")
    def test_gemini_backend_creation(self, mock_class):
        """Test Gemini backend can be created when available."""
        mock_class.return_value = Mock()
        backend = get_backend("gemini", model_path="test")
        assert backend is not None


class TestBackendIntegration:
    """Test backend integration scenarios."""

    def test_backend_lifecycle(self):
        """Test complete backend lifecycle."""

        class MockBackend(BaseBackend):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.load_called = False
                self.unload_called = False
                self.generate_called = False

            def load_model(self):
                self.load_called = True
                self._is_loaded = True

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                if not self.is_loaded():
                    raise BackendError("Model not loaded")
                self.generate_called = True
                return '{"score": 0.8, "verdict": "approve", "comments": ["test"]}'

            def unload_model(self):
                self.unload_called = True
                self._is_loaded = False

        backend = MockBackend("test_model")

        # Initial state
        assert not backend.is_loaded()
        assert not backend.load_called

        # Load model
        backend.load_model()
        assert backend.is_loaded()
        assert backend.load_called

        # Generate response
        response = backend.generate_json("system", "user")  # type: ignore[unreachable]
        assert backend.generate_called
        assert "score" in response

        # Unload model
        backend.unload_model()
        assert not backend.is_loaded()
        assert backend.unload_called

    def test_backend_error_scenarios(self):
        """Test various error scenarios."""

        class ErrorBackend(BaseBackend):
            def load_model(self):
                raise BackendError("Failed to load model")

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                raise BackendError("Generation failed")

            def unload_model(self):
                pass

        backend = ErrorBackend("test_model")

        # Test load error
        with pytest.raises(BackendError, match="Failed to load model"):
            backend.load_model()

        # Test generation error
        with pytest.raises(BackendError, match="Generation failed"):
            backend.generate_json("system", "user")

    def test_backend_parameter_validation(self):
        """Test backend parameter validation."""

        class TestBackend(BaseBackend):
            def load_model(self):
                pass

            def generate_json(self, system_prompt: str, user_prompt: str) -> str:
                return "{}"

            def unload_model(self):
                pass

        # Test valid parameters
        backend = TestBackend(
            model_path="test", device="cuda", temperature=0.5, max_new_tokens=1024, top_p=0.8
        )

        assert backend.device == "cuda"
        assert backend.temperature == 0.5
        assert backend.max_new_tokens == 1024
        assert backend.top_p == 0.8

        # Test default parameters
        backend2 = TestBackend("test")
        assert backend2.device == "cpu"
        assert backend2.temperature == 0.2
        assert backend2.max_new_tokens == 512
        assert backend2.top_p == 0.9
