"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import git
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_git_repo(temp_dir):
    """Create a mock git repository."""
    repo = git.Repo.init(temp_dir)

    # Create initial commit
    test_file = temp_dir / "test.py"
    test_file.write_text("print('hello world')")
    repo.index.add([str(test_file)])
    repo.index.commit("Initial commit")

    return repo


@pytest.fixture
def sample_diff():
    """Sample git diff for testing."""
    return """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    # Added comment
     print("Hello, World!")
     return True"""


@pytest.fixture
def sample_commit_message():
    """Sample commit message for testing."""
    return "feat: add hello function with proper return value"


@pytest.fixture
def mock_model_response():
    """Mock AI model response."""
    return {
        "score": 0.85,
        "verdict": "approve",
        "comments": [
            "Well-structured code changes",
            "Good test coverage",
            "Consider adding documentation",
        ],
    }


@pytest.fixture
def mock_backend():
    """Mock backend for testing."""
    backend = Mock()
    backend.is_loaded.return_value = True
    backend.generate_json.return_value = (
        '{"score": 0.85, "verdict": "approve", "comments": ["Good changes"]}'
    )
    return backend
