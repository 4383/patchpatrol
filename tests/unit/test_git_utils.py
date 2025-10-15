"""Unit tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from patchpatrol.utils.git_utils import (
    GitError,
    GitRepository,
    get_changed_files,
    get_commit_message,
    get_lines_of_change,
    get_staged_diff,
)


class TestGitRepository:
    """Test GitRepository class."""

    def test_init_with_valid_repo(self, mock_git_repo):
        """Test initialization with valid git repo."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))
        assert git_repo.repo_path == str(mock_git_repo.working_dir)
        assert not git_repo._use_subprocess  # Should use GitPython if available

    def test_init_with_invalid_repo(self, temp_dir):
        """Test initialization with invalid git repo."""
        with pytest.raises(GitError, match="Not a Git repository"):
            GitRepository(str(temp_dir))

    def test_init_default_path(self):
        """Test initialization with default path."""
        with patch("os.getcwd", return_value="/current/dir"):
            with patch("patchpatrol.utils.git_utils.Repo") as mock_repo:
                git_repo = GitRepository()
                assert git_repo.repo_path == "/current/dir"
                mock_repo.assert_called_once_with("/current/dir")

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_subprocess_fallback(self, temp_dir):
        """Test subprocess fallback when GitPython not available."""
        # Create a mock git repo directory
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            git_repo = GitRepository(str(temp_dir))
            assert git_repo._use_subprocess is True

    def test_get_staged_diff(self, mock_git_repo):
        """Test getting staged diff."""
        # Create a test file and stage it
        test_file = Path(mock_git_repo.working_dir) / "new_file.py"
        test_file.write_text("def new_function():\n    pass\n")
        mock_git_repo.index.add([str(test_file)])

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        diff = git_repo.get_staged_diff()

        assert "new_file.py" in diff
        assert "def new_function" in diff

    def test_get_staged_diff_with_max_lines(self, mock_git_repo):
        """Test getting staged diff with line limit."""
        # Create a test file with many lines and stage it
        test_file = Path(mock_git_repo.working_dir) / "big_file.py"
        content = "\n".join([f"line_{i}" for i in range(100)])
        test_file.write_text(content)
        mock_git_repo.index.add([str(test_file)])

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        diff = git_repo.get_staged_diff(max_lines=10)

        assert "truncated after 10 lines" in diff

    def test_get_changed_files_staged(self, mock_git_repo):
        """Test getting staged files."""
        # Create and stage a test file
        test_file = Path(mock_git_repo.working_dir) / "staged_file.py"
        test_file.write_text("print('staged')")
        mock_git_repo.index.add([str(test_file)])

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        files = git_repo.get_changed_files(staged_only=True)

        assert "staged_file.py" in files

    def test_get_lines_of_change(self, mock_git_repo):
        """Test getting line change counts."""
        # Use subprocess fallback with predictable output
        with patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False):
            git_repo = GitRepository(str(mock_git_repo.working_dir))

            with patch.object(git_repo, "_run_git_command") as mock_run:
                # Mock the git diff --cached --numstat output
                mock_run.return_value = "2\t0\ttest.py\n"

                added, removed = git_repo.get_lines_of_change()

        assert added == 2  # 2 lines added
        assert removed == 0  # No lines removed

    def test_get_commit_message_from_file(self, temp_dir):
        """Test getting commit message from file."""
        commit_file = temp_dir / "COMMIT_EDITMSG"
        commit_file.write_text("feat: add new feature\n\nDetailed description")

        with patch("patchpatrol.utils.git_utils.Repo"):
            git_repo = GitRepository(str(temp_dir))
            message = git_repo.get_commit_message(str(commit_file))

        assert "feat: add new feature" in message

    def test_get_commit_message_no_file(self, temp_dir):
        """Test getting commit message when no file exists."""
        with patch("patchpatrol.utils.git_utils.Repo"):
            git_repo = GitRepository(str(temp_dir))

            with pytest.raises(GitError, match="No commit message found"):
                git_repo.get_commit_message("nonexistent_file")

    def test_has_staged_changes_true(self, mock_git_repo):
        """Test has_staged_changes returns True when changes exist."""
        # Create and stage a test file
        test_file = Path(mock_git_repo.working_dir) / "staged_change.py"
        test_file.write_text("print('staged change')")
        mock_git_repo.index.add([str(test_file)])

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        assert git_repo.has_staged_changes() is True

    def test_has_staged_changes_false(self, mock_git_repo):
        """Test has_staged_changes returns False when no changes exist."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))
        assert git_repo.has_staged_changes() is False

    def test_get_repo_info(self, mock_git_repo):
        """Test getting repository information."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))
        info = git_repo.get_repo_info()

        assert "repo_path" in info
        assert "using_subprocess" in info
        assert "current_branch" in info or "error" in info

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_subprocess_methods(self, temp_dir):
        """Test subprocess-based methods."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            # Mock successful git command responses
            mock_run.side_effect = [
                Mock(returncode=0),  # _check_git_availability check
                Mock(returncode=0),  # _is_git_repo check
                Mock(returncode=0, stdout="diff content"),  # get_staged_diff
                Mock(returncode=0, stdout="file1.py\nfile2.py"),  # get_changed_files
                Mock(returncode=0, stdout="3\t1\tfile.py"),  # get_lines_of_change
            ]

            git_repo = GitRepository(str(temp_dir))

            # Test diff
            diff = git_repo.get_staged_diff()
            assert diff == "diff content"

            # Test changed files
            files = git_repo.get_changed_files()
            assert files == ["file1.py", "file2.py"]

            # Test line counts
            added, removed = git_repo.get_lines_of_change()
            assert added == 3
            assert removed == 1


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_staged_diff_function(self, mock_git_repo):
        """Test get_staged_diff convenience function."""
        # Create and stage a test file
        test_file = Path(mock_git_repo.working_dir) / "convenience_test.py"
        test_file.write_text("print('convenience test')")
        mock_git_repo.index.add([str(test_file)])

        diff = get_staged_diff(str(mock_git_repo.working_dir))
        assert "convenience_test.py" in diff

    def test_get_changed_files_function(self, mock_git_repo):
        """Test get_changed_files convenience function."""
        # Create and stage a test file
        test_file = Path(mock_git_repo.working_dir) / "changed_file.py"
        test_file.write_text("print('changed')")
        mock_git_repo.index.add([str(test_file)])

        files = get_changed_files(str(mock_git_repo.working_dir))
        assert "changed_file.py" in files

    def test_get_lines_of_change_function(self, mock_git_repo):
        """Test get_lines_of_change convenience function."""
        # Mock the get_lines_of_change method to return predictable results
        with patch("patchpatrol.utils.git_utils.GitRepository") as mock_git_repo_class:
            mock_repo_instance = Mock()
            mock_repo_instance.get_lines_of_change.return_value = (2, 0)
            mock_git_repo_class.return_value = mock_repo_instance

            added, removed = get_lines_of_change(str(mock_git_repo.working_dir))

        assert added == 2
        assert removed == 0

    def test_get_commit_message_function(self, temp_dir):
        """Test get_commit_message convenience function."""
        commit_file = temp_dir / "commit_msg"
        commit_file.write_text("fix: resolve issue")

        with patch("patchpatrol.utils.git_utils.Repo"):
            message = get_commit_message(str(commit_file), str(temp_dir))
            assert "fix: resolve issue" in message


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_git_error_inheritance(self):
        """Test that GitError inherits from Exception."""
        error = GitError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_subprocess_timeout_error(self, temp_dir):
        """Test subprocess timeout handling."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),  # _check_git_availability check
                Mock(returncode=0),  # _is_git_repo check succeeds
                subprocess.TimeoutExpired("git", 30),  # Command times out
            ]

            git_repo = GitRepository(str(temp_dir))

            with pytest.raises(GitError, match="Git command timed out"):
                git_repo.get_staged_diff()

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_subprocess_command_not_found(self, temp_dir):
        """Test git command not found error."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                FileNotFoundError(),  # _check_git_availability fails
            ]

            with pytest.raises(GitError, match="Git command not available"):
                GitRepository(str(temp_dir))

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_subprocess_command_failure(self, temp_dir):
        """Test git command failure handling."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),  # _check_git_availability check
                Mock(returncode=0),  # _is_git_repo check succeeds
                Mock(returncode=1, stderr="fatal: not a git repository"),  # Command fails
            ]

            git_repo = GitRepository(str(temp_dir))

            with pytest.raises(GitError, match="Git command failed"):
                git_repo.get_staged_diff()
