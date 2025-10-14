"""
Command-line interface for PatchPatrol.

This module provides the main CLI commands for AI-powered commit review,
including review-changes and review-message for pre-commit hooks.
"""

import logging
import os
import sys
import warnings
from typing import Optional

import click

# Suppress Google AI library warnings before any imports
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_TRACE"] = ""
os.environ["GLOG_minloglevel"] = "2"

from rich.console import Console  # noqa: E402
from rich.logging import RichHandler  # noqa: E402
from rich.table import Table  # noqa: E402

from .backends.base import BackendError, get_backend  # noqa: E402
from .models import DEFAULT_MODELS, MODEL_REGISTRY, get_model_manager, get_model_path  # noqa: E402
from .prompts import (  # noqa: E402
    SYSTEM_REVIEWER,
    USER_TEMPLATE_CHANGES,
    USER_TEMPLATE_COMPLETE,
    USER_TEMPLATE_MESSAGE,
    truncate_diff,
    truncate_message,
)
from .utils.git_utils import GitError, GitRepository  # noqa: E402
from .utils.parsing import ReviewResult, format_review_output, parse_json_response  # noqa: E402

# Initialize rich console
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_time=False, show_path=False)],
)
logger = logging.getLogger(__name__)


def suppress_google_warnings():
    """Suppress verbose Google AI library warnings."""
    # Suppress gRPC/ALTS warnings that appear when using Gemini API
    os.environ["GRPC_VERBOSITY"] = "ERROR"
    os.environ["GRPC_TRACE"] = ""
    os.environ["GLOG_minloglevel"] = "2"

    # Suppress specific Google library warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="google.*")
    warnings.filterwarnings("ignore", message=".*ALTS.*")

    # Set absl logging to only show errors
    try:
        import absl.logging

        absl.logging.set_verbosity(absl.logging.ERROR)
    except ImportError:
        pass


class CLIError(Exception):
    """Base exception for CLI-related errors."""

    pass


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output")
@click.pass_context
def main(ctx, verbose: bool, quiet: bool):
    """
    PatchPatrol - AI-powered commit review for pre-commit hooks.

    Local, offline analysis of Git commits using ONNX or llama.cpp backends.
    """
    ctx.ensure_object(dict)

    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.getLogger().setLevel(logging.WARNING)


# Model management commands
@main.command("list-models")
@click.option("--cached-only", is_flag=True, help="Show only cached models")
def list_models_cmd(cached_only: bool):
    """List available models."""
    manager = get_model_manager()

    if cached_only:
        cached = manager.list_cached_models()
        if not cached:
            console.print("[yellow]No models cached locally.[/yellow]")
            console.print("\nRun 'patchpatrol download-model <name>' to download a model.")
            return

        console.print("[bold]Cached Models:[/bold]")
        for model_name in cached:
            model_info = MODEL_REGISTRY[model_name]
            console.print(f"  • {model_name} ({model_info.backend})")
        return

    # Show all available models
    table = Table(title="Available Models")
    table.add_column("Name", style="cyan")
    table.add_column("Backend", style="green")
    table.add_column("Size", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Cached", style="magenta")

    cached_models = manager.list_cached_models()

    for model_name, model_info in MODEL_REGISTRY.items():
        is_cached = "✓" if model_name in cached_models else "✗"
        size_str = f"{model_info.size_mb}MB"

        table.add_row(model_name, model_info.backend, size_str, model_info.description, is_cached)

    console.print(table)

    # Show aliases
    console.print("\n[bold]Quick Access Aliases:[/bold]")
    for alias, model_name in DEFAULT_MODELS.items():
        console.print(f"  • {alias} → {model_name}")


@main.command("download-model")
@click.argument("model_name")
@click.option("--force", is_flag=True, help="Force re-download even if cached")
def download_model_cmd(model_name: str, force: bool):
    """Download a model to local cache."""
    manager = get_model_manager()

    try:
        if not force and manager.is_model_cached(model_name):
            console.print(f"[green]Model '{model_name}' is already cached.[/green]")
            model_path = manager.get_model_path(model_name)
            console.print(f"Path: {model_path}")
            return

        with console.status(f"[bold green]Downloading {model_name}..."):
            model_path = manager.download_model(model_name, force=force)

        console.print(f"[green]✓ Successfully downloaded {model_name}[/green]")
        console.print(f"Path: {model_path}")

    except Exception as e:
        console.print(f"[red]✗ Failed to download {model_name}: {e}[/red]")
        sys.exit(1)


@main.command("remove-model")
@click.argument("model_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def remove_model_cmd(model_name: str, yes: bool):
    """Remove a cached model."""
    manager = get_model_manager()

    if not manager.is_model_cached(model_name):
        console.print(f"[yellow]Model '{model_name}' is not cached.[/yellow]")
        return

    if not yes:
        if not click.confirm(f"Remove cached model '{model_name}'?"):
            console.print("Cancelled.")
            return

    if manager.remove_model(model_name):
        console.print(f"[green]✓ Removed {model_name}[/green]")
    else:
        console.print(f"[red]✗ Failed to remove {model_name}[/red]")
        sys.exit(1)


@main.command("cache-info")
def cache_info_cmd():
    """Show model cache information."""
    manager = get_model_manager()

    cached_models = manager.list_cached_models()
    cache_size = manager.get_cache_size()
    cache_size_mb = cache_size / (1024 * 1024)

    table = Table(title="Cache Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Cache Directory", str(manager.cache_dir))
    table.add_row("Cached Models", str(len(cached_models)))
    table.add_row("Total Size", f"{cache_size_mb:.1f} MB")

    console.print(table)

    if cached_models:
        console.print("\n[bold]Cached Models:[/bold]")
        for model_name in cached_models:
            model_info = MODEL_REGISTRY[model_name]
            console.print(f"  • {model_name} ({model_info.size_mb}MB, {model_info.backend})")


@main.command("clean-cache")
@click.option("--keep", multiple=True, help="Models to keep (remove all others)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def clean_cache_cmd(keep: tuple, yes: bool):
    """Clean the model cache."""
    manager = get_model_manager()

    keep_models = list(keep) if keep else []
    cached_models = manager.list_cached_models()

    to_remove = [m for m in cached_models if m not in keep_models]

    if not to_remove:
        console.print("[green]Nothing to clean.[/green]")
        return

    console.print(f"[yellow]Will remove {len(to_remove)} models:[/yellow]")
    for model in to_remove:
        console.print(f"  • {model}")

    if keep_models:
        console.print(f"\n[green]Will keep {len(keep_models)} models:[/green]")
        for model in keep_models:
            console.print(f"  • {model}")

    if not yes:
        if not click.confirm("Proceed with cleanup?"):
            console.print("Cancelled.")
            return

    removed_count = manager.clean_cache(keep_models)
    console.print(f"[green]✓ Removed {removed_count} models[/green]")


@main.command("test-gemini")
@click.option("--api-key", help="Gemini API key (uses GEMINI_API_KEY env var if not provided)")
def test_gemini_cmd(api_key: Optional[str]):
    """Test Gemini API connectivity."""
    suppress_google_warnings()

    try:
        from .backends.gemini_backend import test_gemini_connection

        if test_gemini_connection(api_key):
            console.print("[green]✓ Gemini API connection successful![/green]")
        else:
            console.print("[red]✗ Gemini API connection failed[/red]")
            console.print("\nTroubleshooting:")
            console.print("1. Check your API key: https://makersuite.google.com/app/apikey")
            console.print("2. Set GEMINI_API_KEY environment variable")
            console.print(
                "3. Ensure you have google-generativeai installed: pip install patchpatrol[gemini]"
            )
            sys.exit(1)

    except ImportError:
        console.print("[red]✗ Gemini backend not available[/red]")
        console.print("Install with: pip install patchpatrol[gemini]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error testing Gemini: {e}[/red]")
        sys.exit(1)


@main.command("review-changes")
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["onnx", "llama", "gemini"], case_sensitive=False),
    default=None,
    help="AI inference backend (auto-detected from model if not specified)",
)
@click.option(
    "--model",
    "-m",
    required=True,
    help="Model name (from registry) or path to model file/directory",
)
@click.option(
    "--device",
    type=click.Choice(["cpu", "cuda"], case_sensitive=False),
    default="cpu",
    help="Compute device for inference",
)
@click.option(
    "--threshold",
    "-t",
    type=click.FloatRange(0.0, 1.0),
    default=0.7,
    help="Minimum acceptance score (0.0-1.0)",
)
@click.option(
    "--temperature",
    type=click.FloatRange(0.0, 1.0),
    default=0.2,
    help="Sampling temperature for generation",
)
@click.option(
    "--max-new-tokens",
    type=click.IntRange(min=1),
    default=512,
    help="Maximum new tokens to generate",
)
@click.option(
    "--top-p", type=click.FloatRange(0.0, 1.0), default=0.9, help="Top-p sampling parameter"
)
@click.option(
    "--soft/--hard", default=True, help="Soft mode (warnings) vs hard mode (blocking errors)"
)
@click.option(
    "--repo-path",
    type=click.Path(exists=True),
    help="Path to Git repository (default: current directory)",
)
def review_changes(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
):
    """
    Review staged changes before commit (pre-commit hook).

    Analyzes the staged diff for code quality, structure, and best practices.
    """
    try:
        exit_code = _review_changes_impl(
            backend=backend,
            model=model,
            device=device,
            threshold=threshold,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_p=top_p,
            soft=soft,
            repo_path=repo_path,
        )
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Review failed: {e}")
        if logger.level <= logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@main.command("review-message")
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["onnx", "llama", "gemini"], case_sensitive=False),
    default=None,
    help="AI inference backend (auto-detected from model if not specified)",
)
@click.option(
    "--model",
    "-m",
    required=True,
    help="Model name (from registry) or path to model file/directory",
)
@click.option(
    "--device",
    type=click.Choice(["cpu", "cuda"], case_sensitive=False),
    default="cpu",
    help="Compute device for inference",
)
@click.option(
    "--threshold",
    "-t",
    type=click.FloatRange(0.0, 1.0),
    default=0.7,
    help="Minimum acceptance score (0.0-1.0)",
)
@click.option(
    "--temperature",
    type=click.FloatRange(0.0, 1.0),
    default=0.2,
    help="Sampling temperature for generation",
)
@click.option(
    "--max-new-tokens",
    type=click.IntRange(min=1),
    default=512,
    help="Maximum new tokens to generate",
)
@click.option(
    "--top-p", type=click.FloatRange(0.0, 1.0), default=0.9, help="Top-p sampling parameter"
)
@click.option(
    "--soft/--hard", default=True, help="Soft mode (warnings) vs hard mode (blocking errors)"
)
@click.option(
    "--repo-path",
    type=click.Path(exists=True),
    help="Path to Git repository (default: current directory)",
)
@click.argument("commit_msg_file", required=False)
def review_message(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
    commit_msg_file: Optional[str],
):
    """
    Review commit message (commit-msg hook).

    Analyzes the commit message for clarity, conventions, and alignment with changes.

    COMMIT_MSG_FILE: Path to commit message file (auto-detected if not provided)
    """
    try:
        exit_code = _review_message_impl(
            backend=backend,
            model=model,
            device=device,
            threshold=threshold,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_p=top_p,
            soft=soft,
            repo_path=repo_path,
            commit_msg_file=commit_msg_file,
        )
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Review failed: {e}")
        if logger.level <= logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@main.command("review-complete")
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["onnx", "llama", "gemini"], case_sensitive=False),
    default=None,
    help="AI inference backend (auto-detected from model if not specified)",
)
@click.option(
    "--model",
    "-m",
    required=True,
    help="Model name (from registry) or path to model file/directory",
)
@click.option(
    "--device",
    type=click.Choice(["cpu", "cuda"], case_sensitive=False),
    default="cpu",
    help="Compute device for inference",
)
@click.option(
    "--threshold",
    "-t",
    type=click.FloatRange(0.0, 1.0),
    default=0.7,
    help="Minimum acceptance score (0.0-1.0)",
)
@click.option(
    "--temperature",
    type=click.FloatRange(0.0, 1.0),
    default=0.2,
    help="Sampling temperature for generation",
)
@click.option(
    "--max-new-tokens",
    type=click.IntRange(min=1),
    default=512,
    help="Maximum new tokens to generate",
)
@click.option(
    "--top-p", type=click.FloatRange(0.0, 1.0), default=0.9, help="Top-p sampling parameter"
)
@click.option(
    "--soft/--hard", default=True, help="Soft mode (warnings) vs hard mode (blocking errors)"
)
@click.option(
    "--repo-path",
    type=click.Path(exists=True),
    help="Path to Git repository (default: current directory)",
)
@click.argument("commit_msg_file", required=False)
def review_complete(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
    commit_msg_file: Optional[str],
):
    """
    Review both staged changes and commit message together.

    Performs a comprehensive review of the entire commit.
    """
    try:
        exit_code = _review_complete_impl(
            backend=backend,
            model=model,
            device=device,
            threshold=threshold,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_p=top_p,
            soft=soft,
            repo_path=repo_path,
            commit_msg_file=commit_msg_file,
        )
        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Review failed: {e}")
        if logger.level <= logging.DEBUG:
            console.print_exception()
        sys.exit(1)


def _review_changes_impl(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
) -> int:
    """Implementation for review-changes command."""
    console.print("[bold blue]🔍 PatchPatrol - Reviewing staged changes...[/bold blue]")

    # Initialize Git repository
    repo = GitRepository(repo_path)

    # Check for staged changes
    if not repo.has_staged_changes():
        console.print("[yellow]⚠ No staged changes found. Nothing to review.[/yellow]")
        return 0

    # Get staged diff and file information
    diff = repo.get_staged_diff()
    files = repo.get_changed_files()
    lines_added, lines_removed = repo.get_lines_of_change()

    if not diff.strip():
        console.print("[yellow]⚠ No meaningful changes to review.[/yellow]")
        return 0

    console.print(f"[dim]Files: {', '.join(files) if files else 'unknown'}[/dim]")
    console.print(f"[dim]Changes: +{lines_added} -{lines_removed} lines[/dim]")

    # Truncate diff if needed
    diff = truncate_diff(diff)

    # Prepare prompts
    user_prompt = USER_TEMPLATE_CHANGES.format(
        diff=diff,
        files=", ".join(files) if files else "unknown",
        loc=lines_added + lines_removed,
        threshold=threshold,
    )

    # Run AI review
    result = _run_ai_review(
        backend=backend,
        model=model,
        device=device,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        top_p=top_p,
        system_prompt=SYSTEM_REVIEWER,
        user_prompt=user_prompt,
    )

    # Display results and determine exit code
    return _handle_review_result(result, threshold, soft, "staged changes")


def _review_message_impl(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
    commit_msg_file: Optional[str],
) -> int:
    """Implementation for review-message command."""
    console.print("[bold blue]📝 PatchPatrol - Reviewing commit message...[/bold blue]")

    # Initialize Git repository
    repo = GitRepository(repo_path)

    # Get commit message
    try:
        message = repo.get_commit_message(commit_msg_file)
    except GitError as e:
        console.print(f"[red]✗ Could not read commit message: {e}[/red]")
        return 1

    if not message.strip():
        console.print("[yellow]⚠ Empty commit message.[/yellow]")
        return 1 if not soft else 0

    console.print(f"[dim]Message length: {len(message)} characters[/dim]")

    # Truncate message if needed
    message = truncate_message(message)

    # Prepare prompts
    user_prompt = USER_TEMPLATE_MESSAGE.format(
        message=message,
        threshold=threshold,
    )

    # Run AI review
    result = _run_ai_review(
        backend=backend,
        model=model,
        device=device,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        top_p=top_p,
        system_prompt=SYSTEM_REVIEWER,
        user_prompt=user_prompt,
    )

    # Display results and determine exit code
    return _handle_review_result(result, threshold, soft, "commit message")


def _review_complete_impl(
    backend: Optional[str],
    model: str,
    device: str,
    threshold: float,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    soft: bool,
    repo_path: Optional[str],
    commit_msg_file: Optional[str],
) -> int:
    """Implementation for review-complete command."""
    console.print("[bold blue]🔍📝 PatchPatrol - Comprehensive commit review...[/bold blue]")

    # Initialize Git repository
    repo = GitRepository(repo_path)

    # Get commit message
    try:
        message = repo.get_commit_message(commit_msg_file)
    except GitError as e:
        console.print(f"[red]✗ Could not read commit message: {e}[/red]")
        return 1

    # Get staged changes
    if not repo.has_staged_changes():
        console.print("[yellow]⚠ No staged changes found.[/yellow]")
        return 1 if not soft else 0

    diff = repo.get_staged_diff()
    files = repo.get_changed_files()
    lines_added, lines_removed = repo.get_lines_of_change()

    console.print(f"[dim]Files: {', '.join(files) if files else 'unknown'}[/dim]")
    console.print(f"[dim]Changes: +{lines_added} -{lines_removed} lines[/dim]")
    console.print(f"[dim]Message length: {len(message)} characters[/dim]")

    # Truncate content if needed
    diff = truncate_diff(diff)
    message = truncate_message(message)

    # Prepare prompts
    user_prompt = USER_TEMPLATE_COMPLETE.format(
        message=message,
        diff=diff,
        files=", ".join(files) if files else "unknown",
        loc=lines_added + lines_removed,
        threshold=threshold,
    )

    # Run AI review
    result = _run_ai_review(
        backend=backend,
        model=model,
        device=device,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        top_p=top_p,
        system_prompt=SYSTEM_REVIEWER,
        user_prompt=user_prompt,
    )

    # Display results and determine exit code
    return _handle_review_result(result, threshold, soft, "complete commit")


def _run_ai_review(
    backend: Optional[str],
    model: str,
    device: str,
    temperature: float,
    max_new_tokens: int,
    top_p: float,
    system_prompt: str,
    user_prompt: str,
) -> ReviewResult:
    """Run AI review with specified backend and prompts."""
    try:
        # Resolve model path (download if needed) and detect backend
        model_path, detected_backend = _resolve_model_path(model, backend)

        # Use detected backend if none was specified
        final_backend = backend or detected_backend

        # Suppress Google warnings if using Gemini backend
        if final_backend == "gemini":
            suppress_google_warnings()

        logger.debug(f"Using backend: {final_backend}, model: {model_path}")

        # Create backend
        with console.status("[bold green]Loading AI model..."):
            # Temporarily redirect stderr for Gemini to suppress warnings
            if final_backend == "gemini":
                stderr_backup = sys.stderr
                sys.stderr = open(os.devnull, "w")

            try:
                ai_backend = get_backend(
                    backend_type=final_backend,
                    model_path=model_path,
                    device=device,
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    top_p=top_p,
                )
                ai_backend.load_model()
            finally:
                if final_backend == "gemini":
                    sys.stderr.close()
                    sys.stderr = stderr_backup

        # Generate review
        with console.status("[bold green]Analyzing commit..."):
            # Temporarily redirect stderr for Gemini during inference
            if final_backend == "gemini":
                stderr_backup = sys.stderr
                sys.stderr = open(os.devnull, "w")

            try:
                response = ai_backend.generate_json(system_prompt, user_prompt)
            finally:
                if final_backend == "gemini":
                    sys.stderr.close()
                    sys.stderr = stderr_backup

        # Parse response
        result = parse_json_response(response)
        return result

    except BackendError as e:
        logger.error(f"Backend error: {e}")
        raise CLIError(f"AI backend failed: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during AI review: {e}")
        raise CLIError(f"Review failed: {e}") from e


def _resolve_model_path(model: str, backend: Optional[str] = None) -> tuple[str, str]:
    """
    Resolve model path from name or path.

    If model is a registry name, download it if needed.
    If model is a file path, use it directly.

    Returns:
        Tuple of (model_path, detected_backend)
    """
    # Check if it's a file path
    if os.path.exists(model):
        logger.debug(f"Using model path directly: {model}")

        # Auto-detect backend from file extension if not provided
        if backend is None:
            if model.endswith(".gguf") or model.endswith(".ggml"):
                backend = "llama"
            elif os.path.isdir(model):
                # Assume ONNX if it's a directory
                backend = "onnx"
            else:
                backend = "onnx"  # Default fallback
            logger.debug(f"Auto-detected backend from path: {backend}")

        return model, backend

    # Check if it's a model name in registry
    if model in MODEL_REGISTRY or model in DEFAULT_MODELS:
        # Auto-detect backend if not specified
        if backend is None:
            # Resolve alias first
            resolved_name = DEFAULT_MODELS.get(model, model)
            if resolved_name in MODEL_REGISTRY:
                backend = MODEL_REGISTRY[resolved_name].backend
                logger.debug(f"Auto-detected backend from registry: {backend}")

        logger.info(f"Resolving model '{model}' from registry...")

        # This will download if not cached
        model_path = get_model_path(model)
        return model_path, backend

    # Assume it's a direct path that doesn't exist yet
    logger.warning(f"Model '{model}' not found in registry and path doesn't exist")

    # Try to detect backend from extension
    if backend is None:
        if model.endswith(".gguf") or model.endswith(".ggml"):
            backend = "llama"
        else:
            backend = "onnx"  # Default fallback
        logger.debug(f"Auto-detected backend from filename: {backend}")

    return model, backend


def _handle_review_result(
    result: ReviewResult,
    threshold: float,
    soft: bool,
    review_type: str,
) -> int:
    """Handle review result and determine exit code."""
    # Display formatted result
    formatted_output = format_review_output(result, use_colors=True)
    console.print()
    console.print(formatted_output)
    console.print()

    # Check if review passes
    passes_review = result.is_approved(threshold)

    if passes_review:
        console.print(f"[bold green]✓ {review_type.title()} approved![/bold green]")
        return 0
    else:
        if soft:
            console.print(
                f"[bold yellow]⚠ {review_type.title()} needs attention (soft mode - allowing commit)[/bold yellow]"
            )
            return 0
        else:
            console.print(
                f"[bold red]✗ {review_type.title()} rejected (hard mode - blocking commit)[/bold red]"
            )
            return 1


if __name__ == "__main__":
    main()
