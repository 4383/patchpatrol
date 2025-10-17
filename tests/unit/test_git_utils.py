"""Unit tests for git utilities."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from patchpatrol.utils.git_utils import (
    GitError,
    GitRepository,
    get_changed_files,
    get_commit_diff,
    get_commit_files,
    get_commit_info,
    get_commit_lines_of_change,
    get_commit_message,
    get_commit_message_from_sha,
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


class TestCommitReview:
    """Test commit review functionality."""

    def test_get_commit_diff(self, mock_git_repo):
        """Test getting commit diff."""
        # Create a commit with changes
        test_file = Path(mock_git_repo.working_dir) / "commit_test.py"
        test_file.write_text("def test_function():\n    return True\n")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add test function")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        diff = git_repo.get_commit_diff(commit.hexsha)

        assert "commit_test.py" in diff
        assert "def test_function" in diff

    def test_get_commit_diff_with_max_lines(self, mock_git_repo):
        """Test getting commit diff with line limit."""
        # Create a commit with many changes
        test_file = Path(mock_git_repo.working_dir) / "big_commit.py"
        content = "\n".join([f"line_{i} = {i}" for i in range(100)])
        test_file.write_text(content)
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add big file")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        diff = git_repo.get_commit_diff(commit.hexsha, max_lines=10)

        assert "truncated after 10 lines" in diff

    def test_get_commit_message_from_sha(self, mock_git_repo):
        """Test getting commit message from SHA."""
        # Create a commit with a specific message
        test_file = Path(mock_git_repo.working_dir) / "msg_test.py"
        test_file.write_text("print('message test')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit(
            "feat: add message test\n\nDetailed description of changes"
        )

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        message = git_repo.get_commit_message_from_sha(commit.hexsha)

        assert "feat: add message test" in message
        assert "Detailed description" in message

    def test_get_commit_files(self, mock_git_repo):
        """Test getting files changed in a commit."""
        # Create a commit with multiple files
        file1 = Path(mock_git_repo.working_dir) / "file1.py"
        file2 = Path(mock_git_repo.working_dir) / "file2.py"
        file1.write_text("print('file1')")
        file2.write_text("print('file2')")
        mock_git_repo.index.add([str(file1), str(file2)])
        commit = mock_git_repo.index.commit("Add two files")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        files = git_repo.get_commit_files(commit.hexsha)

        assert "file1.py" in files
        assert "file2.py" in files

    def test_get_commit_lines_of_change(self, mock_git_repo):
        """Test getting line counts for a commit."""
        # Use subprocess fallback for predictable testing
        with patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False):
            git_repo = GitRepository(str(mock_git_repo.working_dir))

            with (
                patch.object(git_repo, "_validate_commit_sha"),
                patch.object(git_repo, "_run_git_command") as mock_run,
            ):
                # Mock the git show --numstat output
                mock_run.return_value = "5\t2\ttest.py\n3\t0\tother.py\n"

                added, removed = git_repo.get_commit_lines_of_change("abc123")

        assert added == 8  # 5 + 3 lines added
        assert removed == 2  # 2 lines removed

    def test_get_commit_info(self, mock_git_repo):
        """Test getting comprehensive commit information."""
        # Create a commit with known metadata
        test_file = Path(mock_git_repo.working_dir) / "info_test.py"
        test_file.write_text("print('info test')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("feat: add info test")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        info = git_repo.get_commit_info(commit.hexsha)

        assert info["full_sha"] == commit.hexsha
        assert info["short_sha"] == commit.hexsha[:8]
        assert info["subject"] == "feat: add info test"
        assert "author_name" in info
        assert "author_email" in info
        assert "author_date" in info

    def test_validate_commit_sha_valid(self, mock_git_repo):
        """Test validating a valid commit SHA."""
        # Create a commit to validate
        test_file = Path(mock_git_repo.working_dir) / "validate_test.py"
        test_file.write_text("print('validate')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add validate test")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        # Should not raise any exception
        git_repo._validate_commit_sha(commit.hexsha)

    def test_validate_commit_sha_invalid(self, mock_git_repo):
        """Test validating an invalid commit SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo._validate_commit_sha("invalid_sha_123")

    def test_validate_commit_sha_short_sha(self, mock_git_repo):
        """Test validating with short SHA."""
        # Create a commit
        test_file = Path(mock_git_repo.working_dir) / "short_sha_test.py"
        test_file.write_text("print('short SHA test')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add short SHA test")

        git_repo = GitRepository(str(mock_git_repo.working_dir))
        # Should work with short SHA too
        git_repo._validate_commit_sha(commit.hexsha[:7])

    @patch("patchpatrol.utils.git_utils.GIT_PYTHON_AVAILABLE", False)
    def test_commit_methods_subprocess(self, temp_dir):
        """Test commit methods using subprocess fallback."""
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            # Mock successful git command responses
            mock_run.side_effect = [
                Mock(returncode=0),  # _check_git_availability
                Mock(returncode=0),  # _is_git_repo
                Mock(returncode=0),  # _validate_commit_sha
                Mock(returncode=0, stdout="commit diff content"),  # get_commit_diff
                Mock(returncode=0),  # _validate_commit_sha
                Mock(
                    returncode=0, stdout="feat: test commit message\n\nDetails"
                ),  # get_commit_message_from_sha
                Mock(returncode=0),  # _validate_commit_sha
                Mock(returncode=0, stdout="file1.py\nfile2.py\n"),  # get_commit_files
                Mock(returncode=0),  # _validate_commit_sha
                Mock(returncode=0, stdout="3\t1\tfile.py\n"),  # get_commit_lines_of_change
                Mock(returncode=0),  # _validate_commit_sha
                Mock(
                    returncode=0,
                    stdout="abc123|abc123|John Doe|john@example.com|2023-01-01|Test commit",
                ),  # get_commit_info
            ]

            git_repo = GitRepository(str(temp_dir))

            # Test commit diff
            diff = git_repo.get_commit_diff("abc123")
            assert diff == "commit diff content"

            # Test commit message
            message = git_repo.get_commit_message_from_sha("abc123")
            assert "feat: test commit message" in message

            # Test commit files
            files = git_repo.get_commit_files("abc123")
            assert files == ["file1.py", "file2.py"]

            # Test line counts
            added, removed = git_repo.get_commit_lines_of_change("abc123")
            assert added == 3
            assert removed == 1

            # Test commit info
            info = git_repo.get_commit_info("abc123")
            assert info["full_sha"] == "abc123"
            assert info["author_name"] == "John Doe"


class TestCommitConvenienceFunctions:
    """Test convenience functions for commit operations."""

    def test_get_commit_diff_function(self, mock_git_repo):
        """Test get_commit_diff convenience function."""
        # Create a commit
        test_file = Path(mock_git_repo.working_dir) / "convenience_commit.py"
        test_file.write_text("print('convenience commit test')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add convenience test")

        diff = get_commit_diff(commit.hexsha, str(mock_git_repo.working_dir))
        assert "convenience_commit.py" in diff

    def test_get_commit_message_from_sha_function(self, mock_git_repo):
        """Test get_commit_message_from_sha convenience function."""
        # Create a commit
        test_file = Path(mock_git_repo.working_dir) / "msg_convenience.py"
        test_file.write_text("print('message convenience')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("fix: message convenience test")

        message = get_commit_message_from_sha(commit.hexsha, str(mock_git_repo.working_dir))
        assert "fix: message convenience test" in message

    def test_get_commit_files_function(self, mock_git_repo):
        """Test get_commit_files convenience function."""
        # Create a commit with files
        test_file = Path(mock_git_repo.working_dir) / "files_convenience.py"
        test_file.write_text("print('files convenience')")
        mock_git_repo.index.add([str(test_file)])
        commit = mock_git_repo.index.commit("Add files convenience")

        files = get_commit_files(commit.hexsha, str(mock_git_repo.working_dir))
        assert "files_convenience.py" in files

    def test_get_commit_lines_of_change_function(self, mock_git_repo):
        """Test get_commit_lines_of_change convenience function."""
        with patch("patchpatrol.utils.git_utils.GitRepository") as mock_git_repo_class:
            mock_repo_instance = Mock()
            mock_repo_instance.get_commit_lines_of_change.return_value = (5, 2)
            mock_git_repo_class.return_value = mock_repo_instance

            added, removed = get_commit_lines_of_change("abc123", str(mock_git_repo.working_dir))

        assert added == 5
        assert removed == 2

    def test_get_commit_info_function(self, mock_git_repo):
        """Test get_commit_info convenience function."""
        with patch("patchpatrol.utils.git_utils.GitRepository") as mock_git_repo_class:
            mock_repo_instance = Mock()
            expected_info = {
                "full_sha": "abc123def456",
                "short_sha": "abc123",
                "author_name": "Test Author",
                "subject": "Test commit",
            }
            mock_repo_instance.get_commit_info.return_value = expected_info
            mock_git_repo_class.return_value = mock_repo_instance

            info = get_commit_info("abc123", str(mock_git_repo.working_dir))

        assert info == expected_info


class TestCommitErrorHandling:
    """Test error handling for commit operations."""

    def test_commit_diff_invalid_sha(self, mock_git_repo):
        """Test commit diff with invalid SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo.get_commit_diff("invalid_sha")

    def test_commit_message_invalid_sha(self, mock_git_repo):
        """Test commit message with invalid SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo.get_commit_message_from_sha("invalid_sha")

    def test_commit_files_invalid_sha(self, mock_git_repo):
        """Test commit files with invalid SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo.get_commit_files("invalid_sha")

    def test_commit_lines_invalid_sha(self, mock_git_repo):
        """Test commit lines with invalid SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo.get_commit_lines_of_change("invalid_sha")

    def test_commit_info_invalid_sha(self, mock_git_repo):
        """Test commit info with invalid SHA."""
        git_repo = GitRepository(str(mock_git_repo.working_dir))

        with pytest.raises(GitError, match="Invalid or non-existent commit SHA"):
            git_repo.get_commit_info("invalid_sha")
