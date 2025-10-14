"""
Git utilities for extracting diffs, staged files, and commit messages.

This module provides functions to interact with Git repositories and
extract information needed for commit review.
"""

import logging
import os
import subprocess
from typing import Any, Optional

try:
    import git
    from git import InvalidGitRepositoryError, Repo

    GIT_PYTHON_AVAILABLE = True
except ImportError:
    GIT_PYTHON_AVAILABLE = False
    git = None
    Repo = None
    InvalidGitRepositoryError = Exception

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Base exception for Git-related operations."""

    pass


class GitRepository:
    """
    Git repository interface for commit review operations.

    Provides methods to extract staged diffs, commit messages, and
    file information needed for AI review.
    """

    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize Git repository interface.

        Args:
            repo_path: Path to Git repository (uses current directory if None)
        """
        self.repo_path = repo_path or os.getcwd()
        self._repo = None
        self._use_subprocess = not GIT_PYTHON_AVAILABLE

        if not self._use_subprocess:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError as e:
                raise GitError(f"Not a Git repository: {self.repo_path}") from e
        else:
            # Fallback to subprocess if GitPython is not available
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
            )

            if result.returncode != 0:
                raise GitError(f"Git command failed: {' '.join(['git'] + args)}\n{result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired as e:
            raise GitError(f"Git command timed out: {' '.join(['git'] + args)}") from e
        except FileNotFoundError as e:
            raise GitError("Git command not found. Is Git installed?") from e

    def get_staged_diff(self, max_lines: Optional[int] = None) -> str:
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

    def get_commit_message(self, commit_msg_file: Optional[str] = None) -> str:
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
            return self._repo.git_dir  # type: ignore[no-any-return]

    def has_staged_changes(self) -> bool:
        """Check if there are any staged changes."""
        try:
            if self._use_subprocess:
                _ = self._run_git_command(["diff", "--cached", "--quiet"])
                return False  # No staged changes (command succeeded)
            else:
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


# Convenience functions for common operations
def get_staged_diff(repo_path: Optional[str] = None, max_lines: Optional[int] = None) -> str:
    """Get staged diff from repository."""
    repo = GitRepository(repo_path)
    return repo.get_staged_diff(max_lines)


def get_changed_files(repo_path: Optional[str] = None, staged_only: bool = True) -> list[str]:
    """Get list of changed files."""
    repo = GitRepository(repo_path)
    return repo.get_changed_files(staged_only)


def get_commit_message(
    commit_msg_file: Optional[str] = None, repo_path: Optional[str] = None
) -> str:
    """Get commit message being prepared."""
    repo = GitRepository(repo_path)
    return repo.get_commit_message(commit_msg_file)


def get_lines_of_change(
    repo_path: Optional[str] = None, staged_only: bool = True
) -> tuple[int, int]:
    """Get lines added and removed."""
    repo = GitRepository(repo_path)
    return repo.get_lines_of_change(staged_only)
