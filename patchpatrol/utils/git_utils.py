"""
Git utilities for extracting diffs, staged files, and commit messages.

This module provides functions to interact with Git repositories and
extract information needed for commit review.
"""

import logging
import os
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # For type checking, assume imports succeed
    import git
    from git import InvalidGitRepositoryError, Repo
else:
    # Runtime imports with fallbacks
    try:
        import git
        from git import InvalidGitRepositoryError, Repo

        GIT_PYTHON_AVAILABLE = True
    except ImportError:
        GIT_PYTHON_AVAILABLE = False
        git = None  # type: ignore[assignment]
        Repo = None  # type: ignore[assignment]
        InvalidGitRepositoryError = Exception  # type: ignore[assignment]

# Set availability flag if not set in TYPE_CHECKING block
if TYPE_CHECKING:
    GIT_PYTHON_AVAILABLE = True

logger = logging.getLogger(__name__)


def _check_git_availability() -> bool:
    """Check if Git is available in the system."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=os.name == "nt",  # Use shell on Windows
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


class GitError(Exception):
    """Base exception for Git-related operations."""

    pass


class GitRepository:
    """
    Git repository interface for commit review operations.

    Provides methods to extract staged diffs, commit messages, and
    file information needed for AI review.
    """

    def __init__(self, repo_path: str | None = None):
        """
        Initialize Git repository interface.

        Args:
            repo_path: Path to Git repository (uses current directory if None)
        """
        self.repo_path = repo_path or os.getcwd()
        self._repo: Any = None
        self._use_subprocess = not GIT_PYTHON_AVAILABLE

        if not self._use_subprocess:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError as e:
                raise GitError(f"Not a Git repository: {self.repo_path}") from e
        else:
            # Fallback to subprocess if GitPython is not available
            if not _check_git_availability():
                raise GitError(
                    "Git command not available. Please ensure Git is installed and in PATH."
                )
            if not self._is_git_repo():
                raise GitError(f"Not a Git repository: {self.repo_path}")

    def _is_git_repo(self) -> bool:
        """Check if current directory is a Git repository using subprocess."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
                shell=os.name == "nt",  # Use shell on Windows
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _run_git_command(self, args: list[str]) -> str:
        """
        Run a Git command and return stdout.

        Args:
            args: Git command arguments

        Returns:
            Command output

        Raises:
            GitError: If command fails
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,  # Reasonable timeout for Git operations
                shell=os.name == "nt",  # Use shell on Windows
            )

            if result.returncode != 0:
                raise GitError(f"Git command failed: {' '.join(['git'] + args)}\n{result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired as e:
            raise GitError(f"Git command timed out: {' '.join(['git'] + args)}") from e
        except FileNotFoundError as e:
            git_help = "Git command not found. On Windows, ensure Git is installed and in PATH."
            raise GitError(git_help) from e
        except OSError as e:
            # Handle Windows-specific path or permission issues
            raise GitError(f"Git command failed due to system error: {e}") from e

    def get_staged_diff(self, max_lines: int | None = None) -> str:
        """
        Get the staged diff (changes ready to be committed).

        Args:
            max_lines: Maximum number of lines to return (None for unlimited)

        Returns:
            Staged diff as string

        Raises:
            GitError: If unable to get diff
        """
        try:
            if self._use_subprocess:
                diff = self._run_git_command(["diff", "--cached"])
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                diff = self._repo.git.diff("--cached")

            if max_lines is not None:
                lines = diff.split("\n")
                if len(lines) > max_lines:
                    diff = "\n".join(lines[:max_lines])
                    diff += f"\n... [truncated after {max_lines} lines]"

            return diff

        except Exception as e:
            logger.error(f"Failed to get staged diff: {e}")
            raise GitError(f"Failed to get staged diff: {e}") from e

    def get_changed_files(self, staged_only: bool = True) -> list[str]:
        """
        Get list of changed files.

        Args:
            staged_only: If True, only return staged files

        Returns:
            List of changed file paths

        Raises:
            GitError: If unable to get file list
        """
        try:
            if self._use_subprocess:
                if staged_only:
                    output = self._run_git_command(["diff", "--cached", "--name-only"])
                else:
                    output = self._run_git_command(["diff", "--name-only"])
                files = [f.strip() for f in output.split("\n") if f.strip()]
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                if staged_only:
                    files = [item.a_path for item in self._repo.index.diff("HEAD")]
                else:
                    files = [item.a_path for item in self._repo.index.diff(None)]

            return files

        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            raise GitError(f"Failed to get changed files: {e}") from e

    def get_lines_of_change(self, staged_only: bool = True) -> tuple[int, int]:
        """
        Get the number of lines added and removed.

        Args:
            staged_only: If True, only count staged changes

        Returns:
            Tuple of (lines_added, lines_removed)

        Raises:
            GitError: If unable to get line counts
        """
        try:
            if self._use_subprocess:
                if staged_only:
                    output = self._run_git_command(["diff", "--cached", "--numstat"])
                else:
                    output = self._run_git_command(["diff", "--numstat"])

                lines_added = lines_removed = 0
                for line in output.strip().split("\n"):
                    if line:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            try:
                                added = int(parts[0]) if parts[0] != "-" else 0
                                removed = int(parts[1]) if parts[1] != "-" else 0
                                lines_added += added
                                lines_removed += removed
                            except ValueError:
                                continue  # Skip binary files or malformed lines

            else:
                # Using GitPython
                assert self._repo is not None, "GitPython repo not initialized"
                if staged_only:
                    diffs = self._repo.index.diff("HEAD")
                else:
                    diffs = self._repo.index.diff(None)

                lines_added = lines_removed = 0
                for diff in diffs:
                    if diff.diff:
                        # Parse diff manually for line counts
                        diff_text = diff.diff.decode("utf-8", errors="ignore")
                        for line in diff_text.split("\n"):
                            if line.startswith("+") and not line.startswith("+++"):
                                lines_added += 1
                            elif line.startswith("-") and not line.startswith("---"):
                                lines_removed += 1

            return lines_added, lines_removed

        except Exception as e:
            logger.error(f"Failed to get line counts: {e}")
            raise GitError(f"Failed to get line counts: {e}") from e

    def get_commit_message(self, commit_msg_file: str | None = None) -> str:
        """
        Get the commit message being prepared.

        Args:
            commit_msg_file: Path to commit message file (for commit-msg hook)

        Returns:
            Commit message content

        Raises:
            GitError: If unable to read commit message
        """
        try:
            if commit_msg_file and os.path.exists(commit_msg_file):
                with open(commit_msg_file, encoding="utf-8") as f:
                    return f.read().strip()

            # Fallback: try to get the message being prepared
            git_dir = self._get_git_dir()
            commit_editmsg = os.path.join(git_dir, "COMMIT_EDITMSG")

            if os.path.exists(commit_editmsg):
                with open(commit_editmsg, encoding="utf-8") as f:
                    return f.read().strip()

            raise GitError("No commit message found")

        except Exception as e:
            logger.error(f"Failed to get commit message: {e}")
            raise GitError(f"Failed to get commit message: {e}") from e

    def _get_git_dir(self) -> str:
        """Get the .git directory path."""
        if self._use_subprocess:
            git_dir = self._run_git_command(["rev-parse", "--git-dir"]).strip()
            if not os.path.isabs(git_dir):
                git_dir = os.path.join(self.repo_path, git_dir)
            return git_dir
        else:
            assert self._repo is not None, "GitPython repo not initialized"
            return self._repo.git_dir  # type: ignore[no-any-return]

    def has_staged_changes(self) -> bool:
        """Check if there are any staged changes."""
        try:
            if self._use_subprocess:
                _ = self._run_git_command(["diff", "--cached", "--quiet"])
                return False  # No staged changes (command succeeded)
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                return len(self._repo.index.diff("HEAD")) > 0

        except GitError:
            return True  # Assume there are changes if command fails

    def get_repo_info(self) -> dict[str, Any]:
        """
        Get general repository information.

        Returns:
            Dictionary with repository metadata
        """
        info = {
            "repo_path": self.repo_path,
            "using_subprocess": self._use_subprocess,
        }

        try:
            if self._use_subprocess:
                # Get basic repo info
                branch = self._run_git_command(["branch", "--show-current"]).strip()
                commit_hash = self._run_git_command(["rev-parse", "HEAD"]).strip()
                info.update(
                    {
                        "current_branch": branch,
                        "current_commit": commit_hash[:8],
                    }
                )
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                info.update(
                    {
                        "current_branch": self._repo.active_branch.name,
                        "current_commit": self._repo.head.commit.hexsha[:8],
                    }
                )

        except Exception as e:
            logger.debug(f"Could not get repo info: {e}")
            info["error"] = str(e)

        return info

    def get_commit_diff(self, commit_sha: str, max_lines: int | None = None) -> str:
        """
        Get the diff for a specific commit.

        Args:
            commit_sha: The commit SHA to get diff for
            max_lines: Maximum number of lines to return (None for unlimited)

        Returns:
            Commit diff as string

        Raises:
            GitError: If unable to get commit diff or commit doesn't exist
        """
        try:
            # Validate commit SHA exists
            self._validate_commit_sha(commit_sha)

            if self._use_subprocess:
                diff = self._run_git_command(["show", "--no-merges", commit_sha])
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                commit = self._repo.commit(commit_sha)
                diff = self._repo.git.show("--no-merges", commit.hexsha)

            if max_lines is not None:
                lines = diff.split("\n")
                if len(lines) > max_lines:
                    diff = "\n".join(lines[:max_lines])
                    diff += f"\n... [truncated after {max_lines} lines]"

            return diff

        except Exception as e:
            logger.error(f"Failed to get commit diff for {commit_sha}: {e}")
            raise GitError(f"Failed to get commit diff for {commit_sha}: {e}") from e

    def get_commit_message_from_sha(self, commit_sha: str) -> str:
        """
        Get the commit message for a specific commit SHA.

        Args:
            commit_sha: The commit SHA to get message for

        Returns:
            Commit message content

        Raises:
            GitError: If unable to get commit message or commit doesn't exist
        """
        try:
            # Validate commit SHA exists
            self._validate_commit_sha(commit_sha)

            if self._use_subprocess:
                message = self._run_git_command(["log", "--format=%B", "-n", "1", commit_sha])
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                commit = self._repo.commit(commit_sha)
                message = commit.message

            return message.strip()

        except Exception as e:
            logger.error(f"Failed to get commit message for {commit_sha}: {e}")
            raise GitError(f"Failed to get commit message for {commit_sha}: {e}") from e

    def get_commit_files(self, commit_sha: str) -> list[str]:
        """
        Get list of files changed in a specific commit.

        Args:
            commit_sha: The commit SHA to get files for

        Returns:
            List of changed file paths

        Raises:
            GitError: If unable to get file list or commit doesn't exist
        """
        try:
            # Validate commit SHA exists
            self._validate_commit_sha(commit_sha)

            if self._use_subprocess:
                output = self._run_git_command(["show", "--name-only", "--format=", commit_sha])
                files = [f.strip() for f in output.split("\n") if f.strip()]
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                commit = self._repo.commit(commit_sha)
                files = []
                if commit.parents:
                    diffs = commit.diff(commit.parents[0])
                    files = [item.a_path for item in diffs if item.a_path]
                else:
                    # Initial commit - all files are new
                    diffs = commit.diff(None)
                    files = [item.a_path for item in diffs if item.a_path]

            return files

        except Exception as e:
            logger.error(f"Failed to get commit files for {commit_sha}: {e}")
            raise GitError(f"Failed to get commit files for {commit_sha}: {e}") from e

    def get_commit_lines_of_change(self, commit_sha: str) -> tuple[int, int]:
        """
        Get the number of lines added and removed in a specific commit.

        Args:
            commit_sha: The commit SHA to analyze

        Returns:
            Tuple of (lines_added, lines_removed)

        Raises:
            GitError: If unable to get line counts or commit doesn't exist
        """
        try:
            # Validate commit SHA exists
            self._validate_commit_sha(commit_sha)

            if self._use_subprocess:
                output = self._run_git_command(["show", "--numstat", "--format=", commit_sha])

                lines_added = lines_removed = 0
                for line in output.strip().split("\n"):
                    if line:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            try:
                                added = int(parts[0]) if parts[0] != "-" else 0
                                removed = int(parts[1]) if parts[1] != "-" else 0
                                lines_added += added
                                lines_removed += removed
                            except ValueError:
                                continue  # Skip binary files or malformed lines
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                commit = self._repo.commit(commit_sha)

                lines_added = lines_removed = 0
                if commit.parents:
                    diffs = commit.diff(commit.parents[0])
                    for diff in diffs:
                        if diff.diff:
                            # Parse diff manually for line counts
                            diff_text = diff.diff.decode("utf-8", errors="ignore")
                            for line in diff_text.split("\n"):
                                if line.startswith("+") and not line.startswith("+++"):
                                    lines_added += 1
                                elif line.startswith("-") and not line.startswith("---"):
                                    lines_removed += 1

            return lines_added, lines_removed

        except Exception as e:
            logger.error(f"Failed to get line counts for {commit_sha}: {e}")
            raise GitError(f"Failed to get line counts for {commit_sha}: {e}") from e

    def get_commit_info(self, commit_sha: str) -> dict[str, Any]:
        """
        Get comprehensive information about a specific commit.

        Args:
            commit_sha: The commit SHA to get info for

        Returns:
            Dictionary with commit metadata

        Raises:
            GitError: If unable to get commit info or commit doesn't exist
        """
        try:
            # Validate commit SHA exists
            self._validate_commit_sha(commit_sha)

            if self._use_subprocess:
                # Get commit info in one call for efficiency
                format_str = "%H|%h|%an|%ae|%ad|%s"
                info_output = self._run_git_command(
                    ["log", "--format=" + format_str, "-n", "1", commit_sha]
                )
                parts = info_output.strip().split("|")

                info = {
                    "full_sha": parts[0],
                    "short_sha": parts[1],
                    "author_name": parts[2],
                    "author_email": parts[3],
                    "author_date": parts[4],
                    "subject": parts[5],
                    "commit_sha": commit_sha,
                }
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                commit = self._repo.commit(commit_sha)

                info = {
                    "full_sha": commit.hexsha,
                    "short_sha": commit.hexsha[:8],
                    "author_name": commit.author.name,
                    "author_email": commit.author.email,
                    "author_date": str(commit.authored_datetime),
                    "subject": commit.summary,
                    "commit_sha": commit_sha,
                }

            return info

        except Exception as e:
            logger.error(f"Failed to get commit info for {commit_sha}: {e}")
            raise GitError(f"Failed to get commit info for {commit_sha}: {e}") from e

    def _validate_commit_sha(self, commit_sha: str) -> None:
        """
        Validate that a commit SHA exists in the repository.

        Args:
            commit_sha: The commit SHA to validate

        Raises:
            GitError: If commit SHA doesn't exist or is invalid
        """
        try:
            if self._use_subprocess:
                self._run_git_command(["cat-file", "-e", commit_sha])
            else:
                assert self._repo is not None, "GitPython repo not initialized"
                self._repo.commit(commit_sha)  # This will raise if commit doesn't exist

        except Exception as e:
            raise GitError(f"Invalid or non-existent commit SHA: {commit_sha}") from e


# Convenience functions for common operations
def get_staged_diff(repo_path: str | None = None, max_lines: int | None = None) -> str:
    """Get staged diff from repository."""
    repo = GitRepository(repo_path)
    return repo.get_staged_diff(max_lines)


def get_changed_files(repo_path: str | None = None, staged_only: bool = True) -> list[str]:
    """Get list of changed files."""
    repo = GitRepository(repo_path)
    return repo.get_changed_files(staged_only)


def get_commit_message(commit_msg_file: str | None = None, repo_path: str | None = None) -> str:
    """Get commit message being prepared."""
    repo = GitRepository(repo_path)
    return repo.get_commit_message(commit_msg_file)


def get_lines_of_change(repo_path: str | None = None, staged_only: bool = True) -> tuple[int, int]:
    """Get lines added and removed."""
    repo = GitRepository(repo_path)
    return repo.get_lines_of_change(staged_only)


def get_commit_diff(
    commit_sha: str, repo_path: str | None = None, max_lines: int | None = None
) -> str:
    """Get diff for a specific commit."""
    repo = GitRepository(repo_path)
    return repo.get_commit_diff(commit_sha, max_lines)


def get_commit_message_from_sha(commit_sha: str, repo_path: str | None = None) -> str:
    """Get commit message for a specific commit SHA."""
    repo = GitRepository(repo_path)
    return repo.get_commit_message_from_sha(commit_sha)


def get_commit_files(commit_sha: str, repo_path: str | None = None) -> list[str]:
    """Get list of files changed in a specific commit."""
    repo = GitRepository(repo_path)
    return repo.get_commit_files(commit_sha)


def get_commit_lines_of_change(commit_sha: str, repo_path: str | None = None) -> tuple[int, int]:
    """Get lines added and removed in a specific commit."""
    repo = GitRepository(repo_path)
    return repo.get_commit_lines_of_change(commit_sha)


def get_commit_info(commit_sha: str, repo_path: str | None = None) -> dict[str, Any]:
    """Get comprehensive information about a specific commit."""
    repo = GitRepository(repo_path)
    return repo.get_commit_info(commit_sha)
