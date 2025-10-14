# Contributing to PatchPatrol

Thank you for your interest in contributing to PatchPatrol! This guide will help you set up your development environment and understand our contribution process.

## Development Setup

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/patchpatrol/patchpatrol.git
cd patchpatrol

# Install with development dependencies
uv sync --all-extras
# or with pip: pip install -e .[all]

# Install pre-commit hooks using uvx (no global installation needed)
# uvx runs tools in isolated environments without polluting your system
uvx pre-commit install --install-hooks
```

### 2. Install Pre-commit Hooks

Our pre-commit configuration includes:

**Code Quality Tools:**
- **Black**: Code formatting (100 char line length)
- **isort**: Import sorting
- **Ruff**: Fast Python linting
- **mypy**: Type checking
- **Bandit**: Security linting

**PatchPatrol Self-Review:**
- **Changes Review**: Uses `minimal` model for fast development feedback
- **Message Review**: Uses `cloud` model for commit message quality

### 3. Development Workflow

```bash
# Make your changes
# ...

# Stage your changes
git add .

# Pre-commit hooks will run automatically:
# 1. Code formatting and linting
# 2. PatchPatrol reviews your changes
# 3. PatchPatrol reviews your commit message

# Commit (pre-commit runs again on commit message)
git commit -m "feat: add awesome new feature"
```

### 4. Model Requirements

For development, you'll need either:

**Option A: Local Models (Recommended for Development)**
```bash
# Download a fast local model for development
uv run patchpatrol download-model minimal
```

**Option B: Cloud Models (Requires API Key)**
```bash
# Set up Gemini API key for cloud models
export GEMINI_API_KEY="your-api-key"
uv run patchpatrol test-gemini
```

### 5. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=patchpatrol --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests (slower)
pytest -m integration
```

### 6. Manual Code Quality Checks

```bash
# Format code
black .
isort .

# Lint code
ruff check . --fix

# Type check
mypy patchpatrol/

# Security check
bandit -r patchpatrol/
```

## Pre-commit Hook Configuration

### Default Configuration

The default setup uses:
- **Changes Review**: `minimal` model, soft mode, 0.6 threshold
- **Message Review**: `cloud` model, soft mode, 0.7 threshold

### Customizing for Your Workflow

Edit `.pre-commit-config.yaml` to adjust:

```yaml
# For faster commits (lower quality threshold)
args: [--model=minimal, --soft, --threshold=0.5]

# For stricter quality (higher threshold, hard mode)
args: [--model=premium, --hard, --threshold=0.8]

# For offline-only development (no cloud models)
args: [--model=minimal, --soft, --threshold=0.6]
```

### Alternative Configurations

Uncomment sections in `.pre-commit-config.yaml` for:
- **Quick commits**: Fast local-only review
- **Thorough review**: Comprehensive cloud-based analysis
- **Branch-specific**: Different rules for main vs feature branches

## Understanding PatchPatrol Output

### Review Scores
- **0.9-1.0**: Excellent quality
- **0.8-0.9**: Good quality
- **0.7-0.8**: Acceptable (default threshold)
- **0.6-0.7**: Needs improvement
- **<0.6**: Significant issues

### Soft vs Hard Mode
- **Soft mode** (`--soft`): Shows warnings but allows commits
- **Hard mode** (`--hard`): Blocks commits below threshold

### Common Review Comments
- Missing tests for new functionality
- Incomplete documentation
- Code style inconsistencies
- Security concerns
- Performance implications

## Troubleshooting

### Pre-commit Issues

```bash
# Reinstall hooks
uvx pre-commit uninstall
uvx pre-commit install --install-hooks

# Update hooks to latest versions
uvx pre-commit autoupdate

# Run specific hook manually
uvx pre-commit run black --all-files
uvx pre-commit run patchpatrol-review-changes-dev --all-files

# Run all hooks on all files
uvx pre-commit run --all-files
```

### Model Issues

```bash
# Check available models
uv run patchpatrol list-models

# Test model connectivity
uv run patchpatrol test-gemini  # for cloud models

# Download required models
uv run patchpatrol download-model minimal
```

### Environment Issues

```bash
# Verify installation
uv run patchpatrol --help

# Check dependencies
pip check

# Reset virtual environment
rm -rf .venv
uv sync --all-extras
```

## Contribution Guidelines

1. **Fork and Branch**: Create feature branches from `main`
2. **Small Changes**: Keep PRs focused and atomic
3. **Tests**: Add tests for new functionality
4. **Documentation**: Update docs for user-facing changes
5. **Quality**: Ensure pre-commit hooks pass
6. **Review**: Use PatchPatrol to review your own changes first

## Code Style

- **Line Length**: 100 characters (configured in black/ruff)
- **Type Hints**: Use type hints for public APIs
- **Docstrings**: Use Google-style docstrings
- **Imports**: Follow isort configuration
- **Security**: Follow bandit recommendations

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/patchpatrol/patchpatrol/issues)
- **Discussions**: [GitHub Discussions](https://github.com/patchpatrol/patchpatrol/discussions)
- **Documentation**: README.md and inline code docs

Happy contributing! 🚀
