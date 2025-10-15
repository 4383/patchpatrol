"""Unit tests for CLI module."""

import os
from unittest.mock import Mock, patch

from click.testing import CliRunner

from patchpatrol.cli import (
    CLIError,
    _handle_review_result,
    _resolve_model_path,
    main,
    suppress_google_warnings,
)
from patchpatrol.utils.parsing import ReviewResult


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_error_inheritance(self):
        """Test that CLIError inherits from Exception."""
        error = CLIError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_suppress_google_warnings(self):
        """Test that Google warnings suppression sets environment variables."""
        # Clear any existing env vars
        env_vars = ["GRPC_VERBOSITY", "GRPC_TRACE", "GLOG_minloglevel"]
        for var in env_vars:
            os.environ.pop(var, None)

        suppress_google_warnings()

        assert os.environ["GRPC_VERBOSITY"] == "ERROR"
        assert os.environ["GRPC_TRACE"] == ""
        assert os.environ["GLOG_minloglevel"] == "2"

    def test_main_help(self):
        """Test main command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "PatchPatrol" in result.output
        assert "AI-powered commit review" in result.output

    def test_main_verbose_flag(self):
        """Test verbose flag sets logging level."""
        runner = CliRunner()

        with patch("logging.getLogger") as mock_logger:
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance

            runner.invoke(main, ["--verbose", "list-models"])

            mock_logger_instance.setLevel.assert_called_with(10)  # DEBUG level

    def test_main_quiet_flag(self):
        """Test quiet flag sets logging level."""
        runner = CliRunner()

        with patch("logging.getLogger") as mock_logger:
            mock_logger_instance = Mock()
            mock_logger.return_value = mock_logger_instance

            runner.invoke(main, ["--quiet", "list-models"])

            mock_logger_instance.setLevel.assert_called_with(40)  # ERROR level


class TestModelManagementCommands:
    """Test model management CLI commands."""

    @patch("patchpatrol.cli.get_model_manager")
    def test_list_models_no_cached(self, mock_get_manager):
        """Test list-models command with no cached models."""
        mock_manager = Mock()
        mock_manager.list_cached_models.return_value = []
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["list-models", "--cached-only"])

        assert result.exit_code == 0
        assert "No models cached" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    @patch("patchpatrol.cli.MODEL_REGISTRY")
    def test_list_models_with_cached(self, mock_registry, mock_get_manager):
        """Test list-models command with cached models."""
        mock_manager = Mock()
        mock_manager.list_cached_models.return_value = ["test-model"]
        mock_get_manager.return_value = mock_manager

        mock_model_info = Mock()
        mock_model_info.backend = "onnx"
        mock_registry.__getitem__.return_value = mock_model_info

        runner = CliRunner()
        result = runner.invoke(main, ["list-models", "--cached-only"])

        assert result.exit_code == 0
        assert "test-model" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_download_model_already_cached(self, mock_get_manager):
        """Test download-model when model is already cached."""
        mock_manager = Mock()
        mock_manager.is_model_cached.return_value = True
        mock_manager.get_model_path.return_value = "/path/to/model"
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["download-model", "test-model"])

        assert result.exit_code == 0
        assert "already cached" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_download_model_success(self, mock_get_manager):
        """Test successful model download."""
        mock_manager = Mock()
        mock_manager.is_model_cached.return_value = False
        mock_manager.download_model.return_value = "/path/to/model"
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["download-model", "test-model"])

        assert result.exit_code == 0
        assert "Successfully downloaded" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_download_model_failure(self, mock_get_manager):
        """Test model download failure."""
        mock_manager = Mock()
        mock_manager.is_model_cached.return_value = False
        mock_manager.download_model.side_effect = Exception("Download failed")
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["download-model", "test-model"])

        assert result.exit_code == 1
        assert "Failed to download" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_remove_model_not_cached(self, mock_get_manager):
        """Test remove-model when model is not cached."""
        mock_manager = Mock()
        mock_manager.is_model_cached.return_value = False
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["remove-model", "test-model"])

        assert result.exit_code == 0
        assert "not cached" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_remove_model_success(self, mock_get_manager):
        """Test successful model removal."""
        mock_manager = Mock()
        mock_manager.is_model_cached.return_value = True
        mock_manager.remove_model.return_value = True
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["remove-model", "test-model", "--yes"])

        assert result.exit_code == 0
        assert "Removed" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    @patch("patchpatrol.cli.MODEL_REGISTRY")
    def test_cache_info(self, mock_registry, mock_get_manager):
        """Test cache-info command."""
        mock_manager = Mock()
        mock_manager.list_cached_models.return_value = ["granite-3b-code", "codegemma-2b"]
        mock_manager.get_cache_size.return_value = 1024 * 1024 * 100  # 100MB
        mock_manager.cache_dir = "/path/to/cache"
        mock_get_manager.return_value = mock_manager

        # Mock MODEL_REGISTRY entries
        mock_model_info = Mock()
        mock_model_info.size_mb = 1800
        mock_model_info.backend = "onnx"
        mock_registry.__getitem__.return_value = mock_model_info

        runner = CliRunner()
        result = runner.invoke(main, ["cache-info"])

        assert result.exit_code == 0
        assert "Cache Information" in result.output
        assert "100.0 MB" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_clean_cache_nothing_to_clean(self, mock_get_manager):
        """Test clean-cache when nothing needs cleaning."""
        mock_manager = Mock()
        mock_manager.list_cached_models.return_value = ["model1"]
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["clean-cache", "--keep", "model1", "--yes"])

        assert result.exit_code == 0
        assert "Nothing to clean" in result.output

    @patch("patchpatrol.cli.get_model_manager")
    def test_clean_cache_success(self, mock_get_manager):
        """Test successful cache cleaning."""
        mock_manager = Mock()
        mock_manager.list_cached_models.return_value = ["model1", "model2"]
        mock_manager.clean_cache.return_value = 1
        mock_get_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(main, ["clean-cache", "--keep", "model1", "--yes"])

        assert result.exit_code == 0
        assert "Removed 1 models" in result.output


class TestTestGeminiCommand:
    """Test test-gemini command."""

    @patch("patchpatrol.backends.gemini_backend.test_gemini_connection")
    def test_test_gemini_success(self, mock_test_connection):
        """Test successful Gemini connection test."""
        mock_test_connection.return_value = True

        runner = CliRunner()
        result = runner.invoke(main, ["test-gemini"])

        assert result.exit_code == 0
        assert "connection successful" in result.output

    @patch("patchpatrol.backends.gemini_backend.test_gemini_connection")
    def test_test_gemini_failure(self, mock_test_connection):
        """Test failed Gemini connection test."""
        mock_test_connection.return_value = False

        runner = CliRunner()
        result = runner.invoke(main, ["test-gemini"])

        assert result.exit_code == 1
        assert "connection failed" in result.output

    def test_test_gemini_import_error(self):
        """Test test-gemini when Gemini backend not available."""
        runner = CliRunner()

        with patch.dict("sys.modules", {"patchpatrol.backends.gemini_backend": None}):
            result = runner.invoke(main, ["test-gemini"])

        assert result.exit_code == 1
        assert "not available" in result.output


class TestResolveModelPath:
    """Test _resolve_model_path function."""

    def test_resolve_existing_file_path(self, temp_dir):
        """Test resolving existing file path."""
        model_file = temp_dir / "model.onnx"
        model_file.touch()

        path, backend = _resolve_model_path(str(model_file))

        assert path == str(model_file)
        assert backend == "onnx"  # Auto-detected from .onnx extension

    def test_resolve_existing_directory_path(self, temp_dir):
        """Test resolving existing directory path."""
        model_dir = temp_dir / "model_dir"
        model_dir.mkdir()

        path, backend = _resolve_model_path(str(model_dir))

        assert path == str(model_dir)
        assert backend == "onnx"  # Auto-detected for directories

    def test_resolve_existing_path_with_backend(self, temp_dir):
        """Test resolving existing path with specified backend."""
        model_file = temp_dir / "model.bin"
        model_file.touch()

        path, backend = _resolve_model_path(str(model_file), backend="onnx")

        assert path == str(model_file)
        assert backend == "onnx"  # Uses specified backend

    @patch("patchpatrol.cli.MODEL_REGISTRY")
    @patch("patchpatrol.cli.DEFAULT_MODELS")
    @patch("patchpatrol.cli.get_model_path")
    def test_resolve_registry_model(self, mock_get_path, mock_defaults, mock_registry):
        """Test resolving model from registry."""
        mock_model_info = Mock()
        mock_model_info.backend = "onnx"
        mock_registry.__contains__.return_value = True
        mock_registry.__getitem__.return_value = mock_model_info
        mock_defaults.get.return_value = "test-model"
        mock_get_path.return_value = "/path/to/model"

        path, backend = _resolve_model_path("test-model")

        assert path == "/path/to/model"
        assert backend == "onnx"

    @patch("patchpatrol.cli.MODEL_REGISTRY")
    @patch("patchpatrol.cli.DEFAULT_MODELS")
    @patch("patchpatrol.cli.get_model_path")
    def test_resolve_alias_model(self, mock_get_path, mock_defaults, mock_registry):
        """Test resolving model alias."""
        mock_model_info = Mock()
        mock_model_info.backend = "onnx"
        mock_registry.__contains__.side_effect = lambda x: x == "real-model"
        mock_registry.__getitem__.return_value = mock_model_info
        mock_defaults.get.return_value = "real-model"
        mock_defaults.__contains__.return_value = True
        mock_get_path.return_value = "/path/to/model"

        path, backend = _resolve_model_path("alias", backend=None)

        assert path == "/path/to/model"
        assert backend == "onnx"

    def test_resolve_nonexistent_model(self):
        """Test resolving non-existent model."""
        path, backend = _resolve_model_path("nonexistent.onnx")

        assert path == "nonexistent.onnx"
        assert backend == "onnx"  # Auto-detected from extension

    def test_resolve_unknown_extension(self):
        """Test resolving model with unknown extension."""
        path, backend = _resolve_model_path("model.unknown")

        assert path == "model.unknown"
        assert backend == "onnx"  # Default fallback


class TestHandleReviewResult:
    """Test _handle_review_result function."""

    def test_handle_approved_result(self):
        """Test handling approved review result."""
        result = ReviewResult(
            score=0.85,
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
        )

        with patch("patchpatrol.cli.console"):
            exit_code = _handle_review_result(result, threshold=0.7, soft=True, review_type="test")

        assert exit_code == 0

    def test_handle_rejected_result_soft_mode(self):
        """Test handling rejected result in soft mode."""
        result = ReviewResult(
            score=0.5,
            verdict="revise",
            comments=["Needs work"],
            raw_response="{}",
        )

        with patch("patchpatrol.cli.console"):
            exit_code = _handle_review_result(result, threshold=0.7, soft=True, review_type="test")

        assert exit_code == 0  # Soft mode allows commit

    def test_handle_rejected_result_hard_mode(self):
        """Test handling rejected result in hard mode."""
        result = ReviewResult(
            score=0.5,
            verdict="revise",
            comments=["Needs work"],
            raw_response="{}",
        )

        with patch("patchpatrol.cli.console"):
            exit_code = _handle_review_result(result, threshold=0.7, soft=False, review_type="test")

        assert exit_code == 1  # Hard mode blocks commit

    def test_handle_low_score_approved_verdict(self):
        """Test handling result with approve verdict but low score."""
        result = ReviewResult(
            score=0.6,
            verdict="approve",
            comments=["Good work"],
            raw_response="{}",
        )

        with patch("patchpatrol.cli.console"):
            exit_code = _handle_review_result(result, threshold=0.7, soft=False, review_type="test")

        assert exit_code == 1  # Should fail due to low score


class TestReviewCommands:
    """Test review command CLI interfaces."""

    @patch("patchpatrol.cli._review_changes_impl")
    def test_review_changes_command(self, mock_impl):
        """Test review-changes command interface."""
        mock_impl.return_value = 0

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--backend",
                "onnx",
                "--threshold",
                "0.8",
            ],
        )

        mock_impl.assert_called_once()
        args, kwargs = mock_impl.call_args
        assert kwargs["threshold"] == 0.8
        assert kwargs["backend"] == "onnx"
        assert kwargs["model"] == "test-model"

    @patch("patchpatrol.cli._review_message_impl")
    def test_review_message_command(self, mock_impl):
        """Test review-message command interface."""
        mock_impl.return_value = 0

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "review-message",
                "--model",
                "test-model",
                "--soft",
                "commit.msg",
            ],
        )

        mock_impl.assert_called_once()
        args, kwargs = mock_impl.call_args
        assert kwargs["soft"] is True
        assert kwargs["model"] == "test-model"
        assert kwargs["commit_msg_file"] == "commit.msg"

    @patch("patchpatrol.cli._review_complete_impl")
    def test_review_complete_command(self, mock_impl):
        """Test review-complete command interface."""
        mock_impl.return_value = 0

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "review-complete",
                "--model",
                "test-model",
                "--hard",
            ],
        )

        mock_impl.assert_called_once()
        args, kwargs = mock_impl.call_args
        assert kwargs["soft"] is False
        assert kwargs["model"] == "test-model"

    @patch("patchpatrol.cli._review_changes_impl")
    def test_review_changes_exception_handling(self, mock_impl):
        """Test review-changes exception handling."""
        mock_impl.side_effect = Exception("Test error")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
            ],
        )

        assert result.exit_code == 1

    def test_review_changes_required_model(self):
        """Test that review-changes requires --model argument."""
        runner = CliRunner()
        result = runner.invoke(main, ["review-changes"])

        assert result.exit_code == 2  # Click error for missing required option
        assert "Missing option" in result.output or "--model" in result.output


class TestParameterValidation:
    """Test CLI parameter validation."""

    def test_threshold_range_validation(self):
        """Test threshold parameter range validation."""
        runner = CliRunner()

        # Test invalid threshold (too high)
        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--threshold",
                "1.5",
            ],
        )
        assert result.exit_code == 2

        # Test invalid threshold (too low)
        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--threshold",
                "-0.1",
            ],
        )
        assert result.exit_code == 2

    def test_temperature_range_validation(self):
        """Test temperature parameter range validation."""
        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--temperature",
                "2.0",
            ],
        )
        assert result.exit_code == 2

    def test_max_new_tokens_validation(self):
        """Test max-new-tokens parameter validation."""
        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--max-new-tokens",
                "0",
            ],
        )
        assert result.exit_code == 2

    def test_valid_backend_choices(self):
        """Test backend parameter choices."""
        runner = CliRunner()

        # Valid backend
        with patch("patchpatrol.cli._review_changes_impl") as mock_impl:
            mock_impl.return_value = 0
            result = runner.invoke(
                main,
                [
                    "review-changes",
                    "--model",
                    "test-model",
                    "--backend",
                    "onnx",
                ],
            )
            assert result.exit_code == 0

        # Invalid backend
        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--backend",
                "invalid",
            ],
        )
        assert result.exit_code == 2

    def test_valid_device_choices(self):
        """Test device parameter choices."""
        runner = CliRunner()

        # Valid device
        with patch("patchpatrol.cli._review_changes_impl") as mock_impl:
            mock_impl.return_value = 0
            result = runner.invoke(
                main,
                [
                    "review-changes",
                    "--model",
                    "test-model",
                    "--device",
                    "cuda",
                ],
            )
            assert result.exit_code == 0

        # Invalid device
        result = runner.invoke(
            main,
            [
                "review-changes",
                "--model",
                "test-model",
                "--device",
                "tpu",
            ],
        )
        assert result.exit_code == 2
