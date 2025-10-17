<div align="center">
  <img src="https://raw.githubusercontent.com/4383/patchpatrol/main/logo.png" alt="PatchPatrol Logo" height="300">
</div>


# PatchPatrol

<div align="center">

[![Tests](https://github.com/4383/patchpatrol/workflows/Tests/badge.svg)](https://github.com/4383/patchpatrol/actions)
[![PyPI version](https://badge.fury.io/py/patchpatrol.svg)](https://badge.fury.io/py/patchpatrol)
[![Python versions](https://img.shields.io/pypi/pyversions/patchpatrol.svg)](https://pypi.org/project/patchpatrol/)
[![Development Status](https://img.shields.io/pypi/status/patchpatrol.svg)](https://pypi.org/project/patchpatrol/)
[![Downloads](https://static.pepy.tech/badge/patchpatrol)](https://pepy.tech/project/patchpatrol)
[![Downloads per month](https://static.pepy.tech/badge/patchpatrol/month)](https://pepy.tech/project/patchpatrol)
[![License](https://img.shields.io/pypi/l/patchpatrol.svg)](https://github.com/4383/patchpatrol/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

**AI-powered commit review system for pre-commit hooks**

PatchPatrol is a flexible AI system that analyzes Git commits for code quality, coherence, and commit message clarity using local models (ONNX/llama.cpp) or cloud APIs (Gemini). Choose between fully offline local inference or powerful cloud-based analysis. It integrates seamlessly with pre-commit hooks to provide automated code review before your changes reach the repository.

## Features

- **Multiple AI Backends**: Local (ONNX/llama.cpp) and cloud (Gemini API) options
- **Privacy Options**: Choose fully offline local models or powerful cloud analysis
- **Automatic Model Management**: Built-in model registry with automatic downloading
- **Zero Setup**: Works out-of-the-box in CI/CD environments
- **Fast Analysis**: Optimized for sub-5-second review cycles (local) or instant cloud responses
- **Structured Output**: Consistent JSON responses with scores and actionable feedback
- **Configurable**: Soft/hard modes, custom thresholds, and extensible prompts
- **Pre-commit Integration**: Drop-in compatibility with existing workflows
- **Rich Output**: Beautiful terminal output with colors and formatting

## Quick Start

### Installation

```bash
# Basic installation
pip install patchpatrol

# With ONNX support
pip install patchpatrol[onnx]

# With llama.cpp support
pip install patchpatrol[llama]

# With Gemini API support
pip install patchpatrol[gemini]

# With all backends
pip install patchpatrol[all]
```

### Basic Usage

1. **List available models:**
   ```bash
   patchpatrol list-models
   ```

2. **Test the CLI (models auto-download):**
   ```bash
   # Review staged changes with auto-downloaded model
   patchpatrol review-changes --model granite-3b-code

   # Review commit message with minimal model
   patchpatrol review-message --model minimal

   # Review a specific commit by SHA
   patchpatrol review-commit --model ci abc123d

   # Use cloud-based Gemini API (set GEMINI_API_KEY env var)
   export GEMINI_API_KEY="your-api-key"
   patchpatrol review-changes --model cloud

   # Backend is auto-detected, or specify explicitly
   patchpatrol review-changes --backend onnx --model distilgpt2-onnx
   patchpatrol review-changes --backend llama --model granite-3b-code
   patchpatrol review-changes --backend gemini --model gemini-2.0-flash-exp
   ```

3. **Add to your pre-commit config:**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: https://github.com/patchpatrol/patchpatrol
       rev: v0.1.0
       hooks:
         - id: patchpatrol-review-changes
           args: [--model=ci, --soft]  # Uses fast CI-optimized model
         - id: patchpatrol-review-message
           args: [--model=cloud, --threshold=0.8]  # Uses Gemini API
   ```

### Perfect for CI/CD

```yaml
# GitHub Actions with local models
- name: AI Code Review (Local)
  run: |
    pip install patchpatrol[llama]
    patchpatrol review-changes --model ci --hard
    # Model downloads automatically on first run

# GitHub Actions with Gemini API
- name: AI Code Review (Gemini)
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  run: |
    pip install patchpatrol[gemini]
    patchpatrol review-changes --model cloud --hard
    # No model download needed, uses API
```

## Detailed Usage

### Command Line Interface

#### Model Management Commands

```bash
# List all available models
patchpatrol list-models

# List only cached models
patchpatrol list-models --cached-only

# Download a specific model
patchpatrol download-model granite-3b-code

# Show cache information
patchpatrol cache-info

# Remove a cached model
patchpatrol remove-model granite-3b-code

# Clean cache (keep only specified models)
patchpatrol clean-cache --keep granite-3b-code --keep minimal

# Test Gemini API connectivity
patchpatrol test-gemini --api-key your-api-key
```

#### Review Commands

All review commands support both model names and file paths.

##### `review-changes` - Analyze Staged Changes

```bash
patchpatrol review-changes [OPTIONS]

Options:
  --backend [onnx|llama|gemini]  Backend (auto-detected if not specified)
  --model NAME_OR_PATH       Model name or path (required)
  --device [cpu|cuda|cloud]  Compute device (default: cpu, cloud for API models)
  --threshold FLOAT          Minimum acceptance score 0.0-1.0 (default: 0.7)
  --temperature FLOAT        Sampling temperature 0.0-1.0 (default: 0.2)
  --max-new-tokens INTEGER   Maximum tokens to generate (default: 512)
  --top-p FLOAT             Top-p sampling 0.0-1.0 (default: 0.9)
  --soft/--hard             Soft warnings vs hard blocking (default: soft)
  --repo-path PATH          Git repository path (default: current)
```

**Examples:**
```bash
# Using local model names (auto-download)
patchpatrol review-changes --model granite-3b-code
patchpatrol review-changes --model ci --hard

# Using cloud models (Gemini API)
export GEMINI_API_KEY="your-api-key"
patchpatrol review-changes --model cloud
patchpatrol review-changes --model gemini-2.0-flash-exp --backend gemini

# Using file paths
patchpatrol review-changes --model ./models/my-model.onnx  # ONNX directory/file
patchpatrol review-changes --model ./models/my-model.gguf  # GGUF file

# Backend auto-detection
patchpatrol review-changes --model distilgpt2-onnx    # auto-detects onnx backend
patchpatrol review-changes --model granite-3b-code    # auto-detects llama backend
patchpatrol review-changes --model cloud              # auto-detects gemini backend
```

##### `review-message` - Analyze Commit Messages

```bash
patchpatrol review-message [OPTIONS] [COMMIT_MSG_FILE]

# Same options as review-changes
# COMMIT_MSG_FILE: Path to commit message file (auto-detected if not provided)
```

##### `review-complete` - Comprehensive Review

```bash
patchpatrol review-complete [OPTIONS] [COMMIT_MSG_FILE]

# Reviews both staged changes and commit message together
```

##### `review-commit` - Analyze Historical Commits

```bash
patchpatrol review-commit [OPTIONS] COMMIT_SHA

Options:
  --backend [onnx|llama|gemini]  Backend (auto-detected if not specified)
  --model NAME_OR_PATH       Model name or path (required)
  --device [cpu|cuda|cloud]  Compute device (default: cpu, cloud for API models)
  --threshold FLOAT          Minimum acceptance score 0.0-1.0 (default: 0.7)
  --temperature FLOAT        Sampling temperature 0.0-1.0 (default: 0.2)
  --max-new-tokens INTEGER   Maximum tokens to generate (default: 512)
  --top-p FLOAT             Top-p sampling 0.0-1.0 (default: 0.9)
  --repo-path PATH          Git repository path (default: current)

# COMMIT_SHA: The commit SHA to review (full or short SHA)
```

**Examples:**
```bash
# Review a specific commit by full SHA
patchpatrol review-commit --model granite-3b-code abc123def456789abcdef123456789abcdef0123

# Review using short SHA (7-8 characters)
patchpatrol review-commit --model ci abc123d

# Review with cloud-based analysis
export GEMINI_API_KEY="your-api-key"
patchpatrol review-commit --model cloud def456a

# Review with custom threshold for historical analysis
patchpatrol review-commit --model quality --threshold 0.8 abc123d

# Review commits from different repository
patchpatrol review-commit --model granite-3b-code --repo-path /path/to/repo abc123d
```

**Use Cases:**
```bash
# Code review for pull requests
patchpatrol review-commit --model quality --threshold 0.85 $COMMIT_SHA

# Learning from historical commits
patchpatrol review-commit --model cloud --threshold 0.6 HEAD~5

# Audit commit quality over time
for sha in $(git log --format="%h" -10); do
  patchpatrol review-commit --model ci $sha
done

# Review a merge commit
patchpatrol review-commit --model granite-8b-code --threshold 0.9 HEAD
```

**Note:** Historical commit reviews always run in "soft mode" (non-blocking) since they're used for analysis rather than enforcement.

### Pre-commit Integration

PatchPatrol provides several pre-configured hooks:

```yaml
repos:
  - repo: https://github.com/patchpatrol/patchpatrol
    rev: v0.1.0
    hooks:
      # Standard hooks
      - id: patchpatrol-review-changes      # Review staged changes (hard mode)
      - id: patchpatrol-review-message      # Review commit message (hard mode)
      - id: patchpatrol-review-complete     # Complete review (hard mode)

      # Soft mode hooks (warnings only)
      - id: patchpatrol-changes-soft        # Review changes (soft mode)
      - id: patchpatrol-message-soft        # Review message (soft mode)
```

### Custom Configuration Examples

#### Team Configuration
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/patchpatrol/patchpatrol
    rev: v0.1.0
    hooks:
      - id: patchpatrol-review-changes
        args:
          - --backend=onnx
          - --model=/shared/models/granite-8b-code/
          - --threshold=0.85
          - --device=cuda
          - --hard
      - id: patchpatrol-review-message
        args:
          - --backend=onnx
          - --model=/shared/models/commit-reviewer-onnx
          - --threshold=0.8
          - --soft
```

#### Developer-specific Configuration
```yaml
# For developers with different hardware/preferences
repos:
  - repo: https://github.com/patchpatrol/patchpatrol
    rev: v0.1.0
    hooks:
      - id: patchpatrol-review-changes
        args:
          - --backend=onnx
          - --model=~/models/granite-3b-code/  # Smaller model for laptops
          - --threshold=0.7
          - --soft                            # Warnings only for dev workflow
```

## Models

### Built-in Model Registry

PatchPatrol includes a curated registry of tested models that download automatically:

| Model Name | Backend | Size | Description | Best For |
|------------|---------|------|-------------|----------|
| `distilgpt2-onnx` | onnx | ~350MB | DistilGPT2 ONNX - Minimal size | Resource-constrained environments |
| `granite-3b-code` | llama | ~1.8GB | IBM Granite 3B - Fast, lightweight | CI/CD, quick reviews |
| `granite-8b-code` | llama | ~4.5GB | IBM Granite 8B - Balanced quality | General use |
| `codellama-7b` | llama | ~4.1GB | Meta CodeLlama 7B - Excellent code review | High-quality analysis |
| `codegemma-2b` | llama | ~1.6GB | Google CodeGemma 2B - Ultra-fast | Quick local reviews |
| `gemini-2.0-flash-exp` | gemini | API | Google Gemini 2.0 Flash Experimental - Latest experimental model | Advanced code analysis |
| `gemini-2.0-flash` | gemini | API | Google Gemini 2.0 Flash - Stable fast model | Quick cloud reviews |
| `gemini-2.5-pro` | gemini | API | Google Gemini 2.5 Pro - Future model (restricted access) | Future advanced analysis |

### Quick Access Aliases

| Alias | Model | Purpose |
|-------|-------|---------|
| `ci` | `granite-3b-code` | Fast CI/CD reviews |
| `dev` | `granite-3b-code` | Development workflow |
| `quality` | `codellama-7b` | High-quality local analysis |
| `minimal` | `codegemma-2b` | Smallest/fastest local option |
| `cloud` | `gemini-2.0-flash` | Fast cloud-based reviews |
| `premium` | `gemini-2.0-flash-exp` | Premium cloud analysis |

### Model Management

```bash
# List all available models
patchpatrol list-models

# Download a specific model
patchpatrol download-model granite-3b-code

# Check cache status
patchpatrol cache-info

# Clean up old models
patchpatrol clean-cache --keep ci --keep quality
```

### Custom Models

You can still use custom models by providing file paths:

```bash
# ONNX models (directory containing model files)
patchpatrol review-changes --model ./my-models/custom-onnx/

# ONNX models (single file)
patchpatrol review-changes --model ./my-models/custom.onnx

# llama.cpp models (GGUF files)
patchpatrol review-changes --model ./my-models/custom.gguf

# Backend auto-detection works with file paths too
patchpatrol review-changes --model ./models/mymodel.onnx  # detects onnx backend
patchpatrol review-changes --model ./models/mymodel.gguf  # detects llama backend
```

### Model Export (Advanced)

For custom ONNX models:

```python
# Export a HuggingFace model to ONNX
from optimum.onnxruntime import ORTModelForCausalLM
from transformers import AutoTokenizer

model = ORTModelForCausalLM.from_pretrained(
    "your-model-name",
    export=True
)
tokenizer = AutoTokenizer.from_pretrained("your-model-name")

model.save_pretrained("./models/custom-onnx")
tokenizer.save_pretrained("./models/custom-onnx")
```

### API Models (Gemini)

For cloud-based models, you need to set up API credentials:

```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"

# Test connectivity
patchpatrol test-gemini

# Use in reviews
patchpatrol review-changes --model gemini-2.0-flash-exp
patchpatrol review-changes --model cloud  # Uses gemini-2.0-flash
```

**Get your API key**: [Google AI Studio](https://makersuite.google.com/app/apikey)

**Benefits of API models:**
- No local storage required (0 MB disk usage)
- Latest model capabilities
- No GPU needed
- Instant startup (no model loading)

**Considerations:**
- Requires internet connection
- API costs (typically $0.001-0.01 per review)
- Data sent to Google (code/commits)
- Rate limiting may apply

## Output Format

PatchPatrol generates structured JSON responses:

```json
{
  "score": 0.85,
  "verdict": "approve",
  "comments": [
    "Well-structured code changes with clear intent",
    "Good test coverage for new functionality",
    "Consider adding inline documentation for complex logic"
  ]
}
```

The CLI presents this as rich, colored output:

```
✓ APPROVE | Score: 0.85

Comments:
  1. Well-structured code changes with clear intent
  2. Good test coverage for new functionality
  3. Consider adding inline documentation for complex logic

✓ Staged changes approved!
```

## Configuration Options

### Modes

- **Soft Mode** (`--soft`): Shows warnings but allows commits to proceed
- **Hard Mode** (`--hard`): Blocks commits that don't meet threshold

### Thresholds

- `0.9-1.0`: Exceptional quality required
- `0.8-0.9`: High quality standard
- `0.7-0.8`: Good quality (default)
- `0.6-0.7`: Basic quality checks
- `<0.6`: Very permissive

### Backend Selection

| Backend | Best For | Requirements |
|---------|----------|--------------|
| `onnx` | High accuracy, custom models | `pip install patchpatrol[onnx]` |
| `llama` | Code-optimized models, GGUF support | `pip install patchpatrol[llama]` |
| `gemini` | Cloud-based, no local storage | `pip install patchpatrol[gemini]` + API key |

## Advanced Usage

### Custom Prompt Templates

Advanced users can customize prompts by modifying environment variables:

```bash
export PATCHPATROL_SYSTEM_PROMPT="Your custom system prompt..."
export PATCHPATROL_USER_TEMPLATE_CHANGES="Your custom diff template..."
```

### Performance Tuning

```bash
# Fast inference
patchpatrol review-changes \
  --temperature 0.1 \
  --max-new-tokens 256 \
  --device cpu

# High quality
patchpatrol review-changes \
  --temperature 0.3 \
  --max-new-tokens 1024 \
  --device cuda

# Cloud-based with Gemini
GEMINI_API_KEY="your-key" patchpatrol review-changes \
  --backend gemini \
  --model gemini-2.0-flash-exp \
  --temperature 0.1
```

### Repository-specific Configuration

Create `.patchpatrol.toml`:

```toml
[patchpatrol]
backend = "llama"          # Can be "onnx", "llama", or "gemini"
model = "granite-3b-code"    # Model name from registry
threshold = 0.8
device = "cuda"            # Ignored for API models
soft_mode = false

[patchpatrol.prompts]
custom_instructions = "Focus on security and performance..."

[patchpatrol.env]
# Environment variables (optional)
gemini_api_key = "your-api-key"  # Or use GEMINI_API_KEY env var
```

## CI/CD Integration

PatchPatrol is perfect for CI/CD pipelines with zero-setup automatic model downloading:

### GitHub Actions

```yaml
name: AI Code Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Fetch full history for commit review
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install PatchPatrol
        run: pip install patchpatrol[llama]

      - name: Review Changes
        run: patchpatrol review-changes --model ci --hard

      - name: Review Recent Commits
        run: |
          # Review the last 3 commits for quality assessment
          for sha in $(git log --format="%h" -3); do
            echo "Reviewing commit $sha..."
            patchpatrol review-commit --model ci $sha
          done

      - name: Review Specific Commit (if specified)
        if: github.event.inputs.commit_sha
        run: patchpatrol review-commit --model quality --threshold 0.8 ${{ github.event.inputs.commit_sha }}
```

### GitLab CI

```yaml
ai_review:
  stage: test
  image: python:3.11
  script:
    - pip install patchpatrol[llama]
    - patchpatrol review-changes --model ci --hard
  only:
    - merge_requests

commit_audit:
  stage: test
  image: python:3.11
  script:
    - pip install patchpatrol[llama]
    # Review commits in the merge request
    - |
      if [ -n "$CI_MERGE_REQUEST_TARGET_BRANCH_SHA" ]; then
        for sha in $(git log --format="%h" ${CI_MERGE_REQUEST_TARGET_BRANCH_SHA}..HEAD); do
          echo "Auditing commit $sha..."
          patchpatrol review-commit --model ci $sha
        done
      fi
  only:
    - merge_requests
  allow_failure: true  # Don't fail pipeline on audit issues
```

### Jenkins

```groovy
pipeline {
    agent any
    stages {
        stage('AI Review') {
            steps {
                sh '''
                    pip install patchpatrol[llama]
                    patchpatrol review-changes --model ci --hard
                '''
            }
        }
    }
}
```

### Docker

```dockerfile
FROM python:3.11-slim

RUN pip install patchpatrol[llama]

# Models will be cached in /root/.cache/patchpatrol/models
VOLUME ["/root/.cache/patchpatrol"]

ENTRYPOINT ["patchpatrol"]
```

### Performance in CI

Models are cached after first download:

| Model | Download Time | First Run | Subsequent Runs |
|-------|---------------|-----------|-----------------|
| `ci` (granite-3b-code) | ~2 min | ~15 sec | ~5 sec |
| `minimal` (codegemma-2b) | ~1.5 min | ~8 sec | ~3 sec |
| `quality` (codellama-7b) | ~3 min | ~20 sec | ~7 sec |

## Development

### Building from Source

```bash
git clone https://github.com/patchpatrol/patchpatrol.git
cd patchpatrol
pip install -e .[all]
```

### Running Tests

```bash
pytest tests/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Requirements

- Python >= 3.10
- Git repository
- One of:
  - ONNX Runtime + Transformers (for ONNX backend)
  - llama-cpp-python (for llama.cpp backend)
  - Google GenerativeAI (for Gemini API backend)

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4GB | 8GB+ |
| Storage | 2GB | 10GB+ |
| CPU | 2 cores | 4+ cores |
| GPU | None | CUDA-compatible (optional) |

## Security & Privacy

### Local Models (ONNX/llama.cpp)
- **No Network Calls**: All inference happens locally
- **No Data Collection**: Your code never leaves your machine
- **Secure by Default**: Models run in isolated processes
- **Audit Trail**: All decisions are logged locally

### Cloud Models (Gemini API)
- **API Communication**: Code/commits sent to Google for analysis
- **Privacy Policy**: Subject to Google's privacy policies
- **Data Handling**: Follow Google AI Studio terms of service
- **API Security**: Uses HTTPS encryption for data transmission
- **No Permanent Storage**: Google doesn't store your code for training (per API terms)

### Choosing Your Privacy Level
- **Maximum Privacy**: Use local models (`--model granite-3b-code`, `--model ci`)
- **Balanced Approach**: Use cloud for public repos, local for sensitive code
- **Cloud Benefits**: Latest AI capabilities, no local storage requirements

## Troubleshooting

### Common Issues

**Model Loading Errors:**
```bash
# Check model path
ls -la ./models/your-model/

# Verify dependencies
pip install patchpatrol[llama] --upgrade
```

**Permission Errors:**
```bash
# Ensure Git repository access
git status

# Check file permissions
chmod +x ~/.local/bin/patchpatrol
```

**Performance Issues:**
```bash
# Reduce context size
patchpatrol review-changes --max-new-tokens 256

# Use CPU-optimized models
patchpatrol review-changes --device cpu
```

### Debug Mode

```bash
patchpatrol --verbose review-changes --model ./models/debug-model
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- **Issues**: [GitHub Issues](https://github.com/patchpatrol/patchpatrol/issues)
- **Discussions**: [GitHub Discussions](https://github.com/patchpatrol/patchpatrol/discussions)
- **Documentation**: [Full Docs](https://patchpatrol.dev/docs)

---

**Made with care for developers who value code quality**
