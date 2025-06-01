#!/bin/bash
# OCode Global Installation Script
# Enhanced version with multi-action detection and comprehensive tool support

set -e

OCODE_VERSION="0.1.0"
INSTALL_DIR="$HOME/.local/bin"
OCODE_DIR="$HOME/.ocode"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🚀 Installing OCode AI Coding Assistant v${OCODE_VERSION}"
echo "   Enhanced with multi-action detection and 16+ tools"

# Check if Python 3.8+ is available
print_status "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed."
    echo "Please install Python 3.8 or later and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    print_error "Python ${PYTHON_VERSION} found, but Python ${REQUIRED_VERSION}+ is required."
    exit 1
fi

print_success "Python ${PYTHON_VERSION} found"

# Check if pip is available
print_status "Checking pip..."
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is required but not installed."
    echo "Please install pip3 and try again."
    exit 1
fi

print_success "pip3 found"

# Detect installation method and ask user preference
print_status "Detecting installation method..."
if [ -f "pyproject.toml" ] && [ -f "setup.py" ]; then
    print_status "Found source code, installing in development mode..."
    INSTALL_MODE="development"
else
    print_status "Installing from Git repository..."
    INSTALL_MODE="git"
fi

# Ask about virtual environment
echo ""
read -p "Do you want to install in a virtual environment? (recommended) [Y/n]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    USE_VENV=false
    print_warning "Installing globally without virtual environment"
else
    USE_VENV=true
    print_status "Using virtual environment"
fi

# Virtual environment setup
if [ "$USE_VENV" = true ]; then
    VENV_DIR="$HOME/.ocode/venv"

    if [ ! -d "$VENV_DIR" ]; then
        print_status "Creating virtual environment at $VENV_DIR..."
        mkdir -p "$HOME/.ocode"
        python3 -m venv "$VENV_DIR"
    fi

    print_status "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    # Upgrade pip in venv
    pip install --upgrade pip
fi

# Create directories
print_status "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$OCODE_DIR"
mkdir -p "$OCODE_DIR/memory"
mkdir -p "$OCODE_DIR/commands"

# Install OCode
print_status "Installing OCode..."

if [ "$INSTALL_MODE" = "development" ]; then
    # Development installation
    print_status "Installing from source in development mode..."
    pip install -e .
elif [ "$INSTALL_MODE" = "git" ]; then
    # Git installation
    print_status "Installing from Git repository..."
    pip install git+https://github.com/haasonsaas/ocode.git
elif [ -n "$OCODE_INSTALL_URL" ]; then
    # Custom URL installation
    print_status "Installing from URL: $OCODE_INSTALL_URL"
    pip install "$OCODE_INSTALL_URL"
fi

# Install semantic dependencies for enhanced features
echo ""
read -p "Do you want to install semantic features for enhanced context selection? (recommended) [Y/n]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    print_status "Installing semantic dependencies (numpy, sentence-transformers)..."
    pip install numpy sentence-transformers
    print_success "Semantic features installed - you'll get intelligent file selection!"
else
    print_warning "Skipping semantic features - will use keyword-based fallback"
fi

# Check if ocode command is available
if ! command -v ocode &> /dev/null; then
    echo "⚠️  ocode command not found in PATH"
    echo "Adding ~/.local/bin to PATH..."

    # Add to PATH in shell profile
    SHELL_PROFILE=""
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_PROFILE="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_PROFILE="$HOME/.bashrc"
    else
        SHELL_PROFILE="$HOME/.profile"
    fi

    if [ -f "$SHELL_PROFILE" ]; then
        if ! grep -q "export PATH.*\.local/bin" "$SHELL_PROFILE"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_PROFILE"
            echo "✅ Added ~/.local/bin to PATH in $SHELL_PROFILE"
        fi
    fi
fi

# Check for ripgrep
echo "🔍 Checking for ripgrep (rg)..."
if command -v rg &> /dev/null; then
    echo "✅ ripgrep found"
else
    echo "⚠️  ripgrep not found"
    echo "Installing ripgrep for enhanced search performance..."

    # Detect OS and install ripgrep
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_status "Installing ripgrep via Homebrew..."
            brew install ripgrep
        else
            print_warning "Homebrew not found. Please install ripgrep manually:"
            echo "  • Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo "  • Then run: brew install ripgrep"
        fi
    elif [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        print_status "Installing ripgrep via apt..."
        sudo apt-get update && sudo apt-get install -y ripgrep
    elif [ -f /etc/redhat-release ]; then
        # RHEL/CentOS/Fedora
        print_status "Installing ripgrep via dnf..."
        sudo dnf install -y ripgrep
    elif [ -f /etc/arch-release ]; then
        # Arch Linux
        print_status "Installing ripgrep via pacman..."
        sudo pacman -S --noconfirm ripgrep
    else
        print_warning "Could not detect OS. Please install ripgrep manually:"
        echo "  • Visit: https://github.com/BurntSushi/ripgrep#installation"
        echo "  • Or use cargo: cargo install ripgrep"
    fi

    # Check if installation succeeded
    if command -v rg &> /dev/null; then
        print_success "ripgrep installed successfully!"
    else
        print_warning "ripgrep installation failed. OCode will fall back to Python-based search."
    fi
fi

# Check for Ollama
echo "🔍 Checking for Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama found"

    # Check if Ollama is running
    if ! ollama list &> /dev/null; then
        echo "⚠️  Ollama is not running. Starting Ollama service..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl enable ollama
            sudo systemctl start ollama
        else
            echo "Please start Ollama manually: ollama serve"
        fi
    fi

    # Pull default model
    echo "📥 Pulling default model (llama3:8b)..."
    if ! ollama pull llama3:8b; then
        echo "⚠️  Failed to pull llama3:8b. You can pull it later with: ollama pull llama3:8b"
    fi

    # Pull thinking model for advanced tool calling
    echo "📥 Pulling thinking model (MFDoom/deepseek-coder-v2-tool-calling:latest)..."
    if ! ollama pull MFDoom/deepseek-coder-v2-tool-calling:latest; then
        echo "⚠️  Failed to pull thinking model. You can pull it later with: ollama pull MFDoom/deepseek-coder-v2-tool-calling:latest"
    fi
else
    echo "⚠️  Ollama not found"
    echo "OCode requires Ollama to function. Please install Ollama:"
    echo "  • Visit: https://ollama.ai"
    echo "  • Or run: curl -fsSL https://ollama.ai/install.sh | sh"
fi

# Create default configuration
echo "⚙️  Creating default configuration..."
cat > "$OCODE_DIR/settings.json" << EOF
{
  "model": "llama3:8b",
  "thinking_model": "MFDoom/deepseek-coder-v2-tool-calling:latest",
  "temperature": 0.1,
  "max_tokens": 4096,
  "max_context_files": 20,
  "output_format": "text",
  "verbose": false,
  "use_ripgrep": true,
  "permissions": {
    "allow_file_read": true,
    "allow_file_write": true,
    "allow_shell_exec": false,
    "allow_git_ops": true
  },
  "architecture": {
    "enable_advanced_orchestrator": true,
    "enable_stream_processing": true,
    "enable_semantic_context": true,
    "enable_predictive_execution": true,
    "enable_dynamic_context": true,
    "orchestrator_max_concurrent": 5,
    "stream_processor_batch_size": 1048576,
    "semantic_context_max_files": 20,
    "embedding_model": "all-MiniLM-L6-v2",
    "predictive_cache_warm": true,
    "context_expansion_factor": 1.5
  }
}
EOF

echo "✅ Default configuration created at $OCODE_DIR/settings.json"

# Setup shell completion (optional)
echo ""
read -p "Do you want to set up shell completion? [Y/n]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    SHELL_NAME=$(basename "$SHELL")

    case $SHELL_NAME in
        bash)
            COMPLETION_FILE="$HOME/.bashrc"
            COMPLETION_CMD='eval "$(_OCODE_COMPLETE=bash_source ocode)"'
            ;;
        zsh)
            COMPLETION_FILE="$HOME/.zshrc"
            COMPLETION_CMD='eval "$(_OCODE_COMPLETE=zsh_source ocode)"'
            ;;
        fish)
            COMPLETION_FILE="$HOME/.config/fish/config.fish"
            COMPLETION_CMD='eval (env _OCODE_COMPLETE=fish_source ocode)'
            ;;
        *)
            print_warning "Shell completion setup not supported for $SHELL_NAME"
            COMPLETION_FILE=""
            ;;
    esac

    if [ -n "$COMPLETION_FILE" ]; then
        if ! grep -q "_OCODE_COMPLETE" "$COMPLETION_FILE" 2>/dev/null; then
            echo "" >> "$COMPLETION_FILE"
            echo "# OCode completion" >> "$COMPLETION_FILE"
            echo "$COMPLETION_CMD" >> "$COMPLETION_FILE"
            print_success "Shell completion added to $COMPLETION_FILE"
        else
            print_warning "Shell completion already exists in $COMPLETION_FILE"
        fi
    fi
fi

# Test installation
print_status "Testing installation..."
if command -v ocode &> /dev/null; then
    print_success "OCode installed successfully!"
    ocode --help > /dev/null 2>&1
    print_success "OCode help command works"

    # Test multi-action detection
    echo ""
    print_status "Testing enhanced features..."
    if ocode -p "What tools can you use?" --out text | grep -q "comprehensive list" 2>/dev/null; then
        print_success "Enhanced conversation parsing working"
    fi

    echo ""
    print_success "🎉 Installation complete!"
    echo ""
    print_status "🚀 Quick Start:"
    echo "  ocode --help                        # Show help"
    echo "  ocode init                          # Initialize project"
    echo "  ocode -p \"What tools can you use?\"  # List all tools"
    echo "  ocode -p \"Create three reviewer agents\" # Multi-action example"
    echo "  ocode                               # Interactive mode"
    echo ""
    print_status "🔧 Enhanced Features:"
    echo "  • 14+ query categories with smart detection"
    echo "  • Multi-action queries (e.g., \"run tests and commit\")"
    echo "  • 22+ specialized tools for development workflows"
    echo "  • Agent delegation for complex tasks"
    echo "  • Performance-optimized context strategies"
    echo "  • Thinking model for advanced tool calling"
    echo "  • ripgrep integration for 10-100x faster searches"
    echo ""
    print_status "📖 Documentation:"
    echo "  • Installation guide: INSTALL.md"
    echo "  • Conversation parsing: docs/conversation-parsing.md"
    echo "  • Issues: https://github.com/haasonsaas/ocode/issues"
    echo ""
    print_success "Happy coding with OCode! 🚀"
else
    print_error "Installation failed. Please check the errors above."

    if [ "$USE_VENV" = true ]; then
        print_warning "Add the following to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo "export PATH=\"$VENV_DIR/bin:\$PATH\""
    else
        print_warning "You may need to restart your terminal or run:"
        echo "  source ~/.bashrc  # or ~/.zshrc"
    fi
    exit 1
fi
