#!/bin/bash
# Development environment setup script for PatchPatrol

set -e

echo "🔧 Setting up PatchPatrol development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is required but not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install project with all dependencies
echo "📦 Installing PatchPatrol with all dependencies..."
uv sync --all-extras

# Install pre-commit hooks using uvx
echo "🔗 Installing pre-commit hooks..."
uvx pre-commit install --install-hooks

# Download a fast model for development
echo "🤖 Downloading minimal model for development..."
uv run patchpatrol download-model minimal

# Test the setup
echo "🧪 Testing setup..."
uv run patchpatrol --help > /dev/null
uv run patchpatrol list-models --cached-only

echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Make your changes"
echo "  2. Run: git add ."
echo "  3. Run: git commit -m 'your message'"
echo "  4. Pre-commit hooks will automatically review your changes"
echo ""
echo "Optional: Set up Gemini API for cloud models:"
echo "  export GEMINI_API_KEY='your-api-key'"
echo "  uv run patchpatrol test-gemini"
echo ""
echo "Happy coding! 🚀"
