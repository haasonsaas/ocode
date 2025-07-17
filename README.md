[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/haasonsaas-ocode-badge.png)](https://mseep.ai/app/haasonsaas-ocode)

# OCode - Terminal-Native AI Coding Assistant

> **Powered by Ollama Models**

OCode is a sophisticated terminal-native AI coding assistant that provides deep codebase intelligence and autonomous task execution. Built to work seamlessly with local Ollama models, OCode brings enterprise-grade AI assistance directly to your development workflow.

## 🌟 Features

### Core Capabilities
- **Terminal-native workflow** – runs directly in your shell environment
- **Deep codebase intelligence** – automatically maps and understands your entire project
- **Autonomous task execution** – handles multi-step development tasks end-to-end
- **Direct Ollama integration** – streams completions from local/remote Ollama without proxies
- **Extensible plugin layer** – Model Context Protocol (MCP) enables third-party integrations

### What OCode Can Do
| Domain | Capabilities |
|--------|-------------|
| **Code Generation & Modification** | Multi-file refactors, TDD scaffolding, optimization, documentation |
| **Project Understanding** | Architecture analysis, dependency tracking, cross-file reasoning |
| **Development Automation** | Git workflows, test execution, build & CI integration |
| **Data Processing** | JSON/YAML parsing and querying, data validation, format conversion |
| **System Operations** | Process monitoring, environment management, network connectivity testing |
| **Interactive Operations** | Natural language queries, contextual exploration, debugging assistance |

### 🛠️ Available Tools

OCode includes 19+ specialized tools organized by category:

#### **File Operations**
- `file_edit` - Edit and modify source files with precision
- `file_ops` - Read, write, and manage file operations
- `glob` - Pattern-based file discovery and matching
- `find` - Search for files and directories
- `ls` - List directory contents with filtering
- `head_tail` - Read file beginnings and endings
- `wc` - Count lines, words, and characters

#### **Text Processing**
- `grep` - Advanced text search with regex support
- `text_tools` - Text manipulation and formatting
- `diff` - Compare files and show differences

#### **Data Processing**
- `json_yaml` - Parse, query, and manipulate JSON/YAML data with JSONPath
- `notebook_tools` - Work with Jupyter notebooks

#### **System Operations**
- `ps` - Monitor and query system processes
- `env` - Manage environment variables and .env files
- `ping` - Test network connectivity
- `bash` - Execute shell commands safely
- `which` - Locate system commands

#### **Development Tools**
- `git_tools` - Git operations and repository management
- `architect` - Project architecture analysis and documentation
- `agent` - Delegate complex tasks to specialized agents
- `memory_tools` - Manage context and session memory

#### **Integration**
- `mcp` - Model Context Protocol integration
- `curl` - HTTP requests and API testing

## 🚀 Quick Installation

### One-Line Installation

```bash
# Automated installation (recommended)
curl -fsSL https://raw.githubusercontent.com/haasonsaas/ocode/main/scripts/install.sh | bash
```

This will:
- ✅ Check Python 3.8+ and dependencies
- 🐍 Set up virtual environment (optional)
- 📦 Install OCode with enhanced multi-action detection
- 🤖 Configure 19+ specialized tools including data processing and system monitoring
- 🔧 Set up shell completion
- ✨ Test enhanced conversation parsing

### Manual Installation

If you prefer to install manually or need custom setup:

## 🔧 Detailed Installation & Setup

### Prerequisites

**Required:**
- **Python 3.8+** - Check with `python --version` or `python3 --version`
- **pip** - Should come with Python, verify with `pip --version`

**For full functionality:**
- **Ollama** - Local LLM server ([Installation Guide](https://ollama.ai))
- **Git** - For git integration features

### Step 0: Python Environment Setup

**If you don't have Python 3.8+ installed:**

**macOS:**
```bash
# Using Homebrew (recommended)
brew install python@3.11

# Or download from python.org
# https://www.python.org/downloads/
```

**Linux (Ubuntu/Debian):**
```bash
# Update package list
sudo apt update

# Install Python 3.11 and pip
sudo apt install python3.11 python3.11-venv python3.11-pip

# Set as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

**Linux (CentOS/RHEL/Fedora):**
```bash
# Fedora
sudo dnf install python311 python311-pip python311-venv

# CentOS/RHEL (using EPEL)
sudo yum install epel-release
sudo yum install python311 python311-pip
```

**Windows:**
```bash
# Download from python.org and run installer
# https://www.python.org/downloads/windows/
# Make sure to check "Add Python to PATH" during installation

# Or using Chocolatey
choco install python311

# Or using winget
winget install Python.Python.3.11
```

**Verify Python installation:**
```bash
# Check Python version
python3 --version
# or
python --version

# Check pip
python3 -m pip --version
# or
pip --version

# If you get "command not found", try:
python3.11 --version
/usr/bin/python3 --version
```

**Set up virtual environment (strongly recommended):**
```bash
# Create a dedicated directory for OCode
mkdir ~/ocode-workspace
cd ~/ocode-workspace

# Create virtual environment
python3 -m venv ocode-env

# Activate virtual environment
# On macOS/Linux:
source ocode-env/bin/activate

# On Windows:
ocode-env\Scripts\activate

# Your prompt should now show (ocode-env)
# Verify you're in the virtual environment
which python  # Should show path to venv
python --version
```

**If you have permission issues with pip:**
```bash
# Option 1: Use --user flag (installs to user directory)
python3 -m pip install --user --upgrade pip

# Option 2: Use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Option 3: Fix pip permissions (macOS)
sudo chown -R $(whoami) /usr/local/lib/python3.*/site-packages

# Option 4: Use homebrew Python (macOS)
brew install python@3.11
# Then use /opt/homebrew/bin/python3 instead
```

### Step 1: Install Ollama

**macOS:**
```bash
# Using Homebrew (recommended)
brew install ollama

# Or download from https://ollama.ai
```

**Linux:**
```bash
# One-line installer
curl -fsSL https://ollama.ai/install.sh | sh

# Or using package manager
# Ubuntu/Debian
sudo apt install ollama

# Arch Linux
yay -S ollama
```

**Windows:**
```bash
# Download from https://ollama.ai
# Or use WSL with Linux instructions above
```

**Start Ollama:**
```bash
# Start the Ollama service
ollama serve

# In a new terminal, download a model
ollama pull llama3.2
# or
ollama pull codellama
# or
ollama pull gemma2
```

**Verify Ollama is working:**
```bash
# Check if service is running
curl http://localhost:11434/api/version

# Should return something like: {"version":"0.7.1"}

# List available models
ollama list
```

### Step 2: Install OCode

**Method 1: Enhanced Installation Script (Recommended)**
```bash
# Clone and run installation script
git clone https://github.com/haasonsaas/ocode.git
cd ocode
./scripts/install.sh
```

**Method 2: Development Installation**
```bash
# Clone the repository
git clone https://github.com/haasonsaas/ocode.git
cd ocode

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with enhanced features
pip install -e .

# This will install new dependencies for data processing:
# - pyyaml>=6.0 (YAML parsing)
# - jsonpath-ng>=1.5.3 (JSONPath queries)
# - python-dotenv>=1.0.0 (Environment file handling)
```

**Method 3: Direct Git Installation**
```bash
pip install git+https://github.com/haasonsaas/ocode.git
```

**Method 4: Using pipx (Isolated installation)**
```bash
# Install pipx if you don't have it
pip install pipx

# Install ocode
pipx install git+https://github.com/haasonsaas/ocode.git
```

### Step 3: Verify Installation

```bash
# Check if ocode command is available
python -m ocode_python.core.cli --help

# Should show:
# Usage: python -m ocode_python.core.cli [OPTIONS] COMMAND [ARGS]...
# OCode - Terminal-native AI coding assistant powered by Ollama models.
```

**If you get "command not found":** See [Troubleshooting](#-troubleshooting) section below.

### Step 4: Initialize Your First Project

```bash
# Navigate to your project directory
cd /path/to/your/project

# Initialize OCode for this project
python -m ocode_python.core.cli init

# Should output:
# ✓ Initialized OCode in /path/to/your/project
# Configuration: /path/to/your/project/.ocode/settings.json
```

### Step 5: Test Your Setup

```bash
# Set Ollama host (if using default localhost, this isn't needed)
export OLLAMA_HOST=http://localhost:11434

# Test with a simple prompt
python -m ocode_python.core.cli -p "Hello! Tell me about this project."

# Test enhanced multi-action detection
python -m ocode_python.core.cli -p "Run tests and commit if they pass"

# Test comprehensive tool listing
python -m ocode_python.core.cli -p "What tools can you use?"

# Should connect to Ollama and demonstrate enhanced conversation parsing
```

## ✨ Enhanced Features

OCode includes advanced conversation parsing with multi-action detection:

### 🤖 Multi-Action Query Detection
```bash
# These queries now correctly identify multiple required actions:
python -m ocode_python.core.cli -p "Run tests and commit if they pass"           # test_runner + git_commit
python -m ocode_python.core.cli -p "Find all TODO comments and replace them"     # grep + file_edit
python -m ocode_python.core.cli -p "Analyze architecture and write documentation" # architect + file_write
python -m ocode_python.core.cli -p "Create a component and write tests for it"   # file_write + test_runner
python -m ocode_python.core.cli -p "Parse config.json and update environment"    # json_yaml + env
python -m ocode_python.core.cli -p "Monitor processes and kill high CPU ones"    # ps + bash
```

### 🧠 Smart Tool Selection
- **14+ Query Categories**: Agent management, file operations, testing, git, architecture analysis, data processing
- **19+ Specialized Tools**: Comprehensive coverage for development workflows including data processing and system monitoring
- **Context Optimization**: Intelligent file analysis based on query type
- **Agent Delegation**: Recommendations for complex multi-step workflows

### 🚀 Performance Improvements
- **Tool fixation eliminated**: No more defaulting to tool lists
- **Context strategies**: none/minimal/targeted/full based on query complexity
- **Enhanced accuracy**: >97% query categorization accuracy

## 📖 Usage Guide

### Basic Commands

**Interactive Mode:**
```bash
# Start interactive session
python -m ocode_python.core.cli

# Interactive mode commands:
# /help      - Show available commands
# /exit      - Exit OCode
# /model     - Change model
# /clear     - Clear conversation context
# /save      - Save current session
# /load      - Load previous session
```

**Single Prompt Mode:**
```bash
# Ask a question
python -m ocode_python.core.cli -p "Explain the authentication system"

# Request code changes
python -m ocode_python.core.cli -p "Add error handling to the user login function"

# Generate code
python -m ocode_python.core.cli -p "Create a REST API endpoint for user profiles"
```

**Specify Model:**
```bash
# Use a specific model
python -m ocode_python.core.cli -m llama3.2 -p "Review this code for security issues"

# Use a larger model for complex tasks
python -m ocode_python.core.cli -m codellama:70b -p "Refactor the entire payment processing module"
```

**Different Output Formats:**
```bash
# JSON output
python -m ocode_python.core.cli -p "List all functions in main.py" --out json

# Streaming JSON (for real-time processing)
python -m ocode_python.core.cli -p "Generate tests for UserService" --out stream-json
```

### Configuration Management

**View current configuration:**
```bash
python -m ocode_python.core.cli config --list
```

**Get specific setting:**
```bash
python -m ocode_python.core.cli config --get model
python -m ocode_python.core.cli config --get permissions.allow_file_write
```

**Set configuration:**
```bash
python -m ocode_python.core.cli config --set model=llama3.2:latest
python -m ocode_python.core.cli config --set temperature=0.1
python -m ocode_python.core.cli config --set permissions.allow_shell_exec=true
```

**Environment Variables:**
```bash
# Model selection
export OCODE_MODEL="codellama:7b"

# Ollama server location
export OLLAMA_HOST="http://192.168.1.100:11434"

# Enable verbose output
export OCODE_VERBOSE=true

# Custom temperature
export OCODE_TEMPERATURE=0.2
```

### Project Configuration

**Project-specific settings (.ocode/settings.json):**
```json
{
  "model": "llama3.2:latest",
  "max_tokens": 4096,
  "temperature": 0.1,
  "permissions": {
    "allow_file_read": true,
    "allow_file_write": true,
    "allow_shell_exec": false,
    "allow_git_ops": true,
    "allowed_paths": ["/path/to/your/project"],
    "blocked_paths": ["/etc", "/bin", "/usr/bin"]
  }
}
```

## 🎯 Common Usage Patterns

### Code Generation
```bash
# Generate new features
ocode -p "Create a user authentication system with JWT tokens"

# Add functionality to existing code
ocode -p "Add input validation to all API endpoints"

# Generate documentation
ocode -p "Add comprehensive docstrings to all functions in utils.py"
```

### Code Analysis & Review
```bash
# Understand existing code
ocode -p "Explain how the database connection pooling works"

# Security review
ocode -p "Review the payment processing code for security vulnerabilities"

# Performance analysis
ocode -p "Identify performance bottlenecks in the user search functionality"
```

### Testing & Quality Assurance
```bash
# Generate tests
ocode -p "Write comprehensive unit tests for the UserRepository class"

# Fix failing tests
ocode -p "Run the test suite and fix any failing tests"

# Code coverage
ocode -p "Improve test coverage for the authentication module"
```

### Git Integration
```bash
# Smart commits
ocode -p "Create a git commit with a descriptive message for these changes"

# Code review
ocode -p "Review the changes in the current branch and suggest improvements"

# Branch analysis
ocode -p "Compare this branch with main and summarize the changes"
```

### Data Processing & Analysis
```bash
# JSON/YAML processing
ocode -p "Parse the config.json file and extract all database connection strings"

# Data validation
ocode -p "Validate the structure of all YAML files in the configs/ directory"

# JSONPath queries
ocode -p "Query user data: find all users with admin roles using JSONPath"

# Environment management
ocode -p "Load variables from .env.production and compare with current environment"
```

### System Monitoring & Operations
```bash
# Process monitoring
ocode -p "Show all Python processes and their memory usage"

# Performance analysis
ocode -p "Find processes consuming more than 50% CPU and analyze them"

# Network connectivity
ocode -p "Test connectivity to all services defined in docker-compose.yml"

# Environment troubleshooting
ocode -p "Check if all required environment variables are set for production"
```

### Project Management
```bash
# Architecture review
ocode -p "Analyze the current project architecture and suggest improvements"

# Dependency analysis
ocode -p "Review project dependencies and identify outdated packages"

# Migration planning
ocode -p "Create a plan to migrate from Python 3.8 to Python 3.11"
```

## 🔧 Advanced Configuration

### Model Selection Strategy

**For different task types:**
```bash
# Fast responses for simple queries
export OCODE_MODEL="llama3.2:3b"

# Balanced performance for general coding
export OCODE_MODEL="llama3.2:latest"  # Usually 7B-8B

# Complex reasoning and large refactors
export OCODE_MODEL="codellama:70b"

# Specialized coding tasks
export OCODE_MODEL="codellama:latest"
```

### Performance Tuning

**Large codebase optimization:**
```json
{
  "max_context_files": 50,
  "max_tokens": 8192,
  "context_window": 16384,
  "ignore_patterns": [
    ".git", "node_modules", "*.log",
    "dist/", "build/", "*.pyc"
  ]
}
```

**Network optimization:**
```bash
# For remote Ollama instances
export OLLAMA_HOST="http://gpu-server:11434"
export OCODE_TIMEOUT=300  # 5 minute timeout for large requests
```

### Security Configuration

**Restrictive permissions:**
```json
{
  "permissions": {
    "allow_file_read": true,
    "allow_file_write": false,
    "allow_shell_exec": false,
    "allow_git_ops": false,
    "allowed_paths": ["/home/user/projects"],
    "blocked_paths": ["/", "/etc", "/bin", "/usr"],
    "blocked_commands": ["rm", "sudo", "chmod", "chown"]
  }
}
```

**Development permissions:**
```json
{
  "permissions": {
    "allow_file_read": true,
    "allow_file_write": true,
    "allow_shell_exec": true,
    "allow_git_ops": true,
    "allowed_commands": ["npm", "yarn", "pytest", "git"],
    "blocked_commands": ["rm -rf", "sudo", "format"]
  }
}
```

## 🐛 Troubleshooting

### Installation Issues

**Problem: `ocode: command not found`**

*Solution 1: Use the full module path*
```bash
# Use the full Python module path
python -m ocode_python.core.cli --help

# Or if using virtual environment
source venv/bin/activate
python -m ocode_python.core.cli --help
```

*Solution 2: Install and check script location*
```bash
# Install in development mode
pip install -e .

# Find where scripts were installed
pip show ocode | grep Location

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

*Solution 3: Use pipx*
```bash
pip install pipx
pipx install git+https://github.com/haasonsaas/ocode.git
```

**Problem: `ModuleNotFoundError` when importing**

*Solution:*
```bash
# Reinstall dependencies
pip install -e .

# Or force reinstall
pip uninstall ocode
pip install -e .

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

**Problem: Permission denied during installation**

*Solution:*
```bash
# Install without sudo using --user flag
pip install --user ocode

# Or use virtual environment
python -m venv ocode-env
source ocode-env/bin/activate
pip install ocode
```

### Ollama Connection Issues

**Problem: `Failed to connect to Ollama`**

*Diagnosis:*
```bash
# Check if Ollama is running
ps aux | grep ollama

# Check if port is open
netstat -ln | grep 11434
# or
lsof -i :11434

# Test direct connection
curl http://localhost:11434/api/version
```

*Solutions:*
```bash
# Start Ollama service
ollama serve

# Check for different port
export OLLAMA_HOST="http://localhost:11434"

# For Docker installations
docker ps | grep ollama
docker logs ollama-container-name

# Check firewall (Linux)
sudo ufw status
sudo ufw allow 11434

# Check firewall (macOS)
sudo pfctl -sr | grep 11434
```

**Problem: `Model not found` errors**

*Solution:*
```bash
# List available models
ollama list

# Pull required model
ollama pull llama3.2

# Update OCode config to use available model
ocode config --set model=llama3.2:latest

# Or set environment variable
export OCODE_MODEL="llama3.2:latest"
```

**Problem: Slow responses or timeouts**

*Solutions:*
```bash
# Increase timeout
export OCODE_TIMEOUT=600  # 10 minutes

# Use smaller model
export OCODE_MODEL="llama3.2:3b"

# Check system resources
top
df -h
free -h

# Monitor Ollama logs
ollama logs
```

### Configuration Issues

**Problem: Configuration not loading**

*Diagnosis:*
```bash
# Check config file location
ocode config --list

# Verify file exists and is readable
ls -la .ocode/settings.json
cat .ocode/settings.json
```

*Solutions:*
```bash
# Reinitialize project
rm -rf .ocode/
ocode init

# Fix JSON syntax
python -m json.tool .ocode/settings.json

# Reset to defaults
ocode config --set model=llama3.2:latest
```

**Problem: Permission denied errors**

*Solution:*
```bash
# Check current permissions
ocode config --get permissions

# Enable required permissions
ocode config --set permissions.allow_file_write=true
ocode config --set permissions.allow_shell_exec=true

# Add allowed paths
ocode config --set permissions.allowed_paths='["/path/to/project"]'
```

### Performance Issues

**Problem: High memory usage**

*Solutions:*
```bash
# Reduce context size
ocode config --set max_context_files=10
ocode config --set max_tokens=2048

# Use smaller model
export OCODE_MODEL="llama3.2:3b"

# Monitor memory usage
ps aux | grep ollama
htop
```

**Problem: Slow startup**

*Solutions:*
```bash
# Preload model in Ollama
ollama run llama3.2:latest "hello"

# Reduce project scan scope
echo "node_modules/\n.git/\ndist/" >> .ocodeignore

# Use SSD for project files
# Move project to faster storage
```

### Network Issues

**Problem: Connection refused (remote Ollama)**

*Solutions:*
```bash
# Test network connectivity
ping your-ollama-server
telnet your-ollama-server 11434

# Check Ollama server binding
# On Ollama server, ensure it binds to 0.0.0.0:11434
OLLAMA_HOST=0.0.0.0 ollama serve

# Update client configuration
export OLLAMA_HOST="http://your-server-ip:11434"
```

### Model Issues

**Problem: Model gives poor responses**

*Solutions:*
```bash
# Try different models
ocode config --set model=codellama:latest
ocode config --set model=llama3.2:70b

# Adjust temperature
ocode config --set temperature=0.1  # More focused
ocode config --set temperature=0.7  # More creative

# Increase context
ocode config --set max_tokens=8192
ocode config --set max_context_files=30
```

**Problem: Model responses cut off**

*Solutions:*
```bash
# Increase token limit
ocode config --set max_tokens=8192

# Use model with larger context window
export OCODE_MODEL="llama3.2:latest"

# Break large requests into smaller parts
ocode -p "First, analyze the authentication system"
ocode -p "Now suggest improvements for the auth system"
```

### Debugging Commands

**Enable verbose logging:**
```bash
# Environment variable
export OCODE_VERBOSE=true

# CLI flag
ocode -v -p "Debug this issue"

# Config setting
ocode config --set verbose=true
```

**Check system information:**
```bash
# OCode version and config
ocode --help
ocode config --list

# Python environment
python --version
pip list | grep ocode

# Ollama status
ollama list
curl http://localhost:11434/api/version

# System resources
df -h
free -h
ps aux | grep -E "(ollama|ocode)"
```

**Log analysis:**
```bash
# Check OCode logs (if implemented)
tail -f ~/.ocode/logs/ocode.log

# Check system logs
# macOS
log show --predicate 'process CONTAINS "ollama"' --last 1h

# Linux
journalctl -u ollama -f
tail -f /var/log/syslog | grep ollama
```

## 🔌 Model Context Protocol (MCP)

OCode includes full MCP support for extensible AI integrations:

### Starting MCP Server
```bash
# Start OCode MCP server
python -m ocode_python.mcp.server --project-root .

# Or via Docker
docker run -p 8000:8000 ocode-mcp-server
```

### MCP Capabilities
- **Resources**: Project files, structure, dependencies, git status
- **Tools**: All OCode tools (file ops, git, shell, testing)
- **Prompts**: Code review, refactoring, test generation templates

## 🔒 Security

OCode implements enterprise-grade security:

### Permission System
- **Whitelist-first** security model
- **Configurable** file access controls
- **Sandboxed** command execution
- **Blocked dangerous** operations by default

### Safe Defaults
```json
{
  "permissions": {
    "allow_file_read": true,
    "allow_file_write": true,
    "allow_shell_exec": false,
    "blocked_paths": ["/etc", "/bin", "/usr/bin"],
    "blocked_commands": ["rm", "sudo", "chmod"]
  }
}
```

## 📚 Documentation

Additional technical documentation is available in the [docs/](docs/) directory:

- [Manual CLI Testing Guide](docs/manual-cli-testing.md) - Instructions for testing the CLI
- [Reliability Improvements](docs/reliability-improvements.md) - Recent enhancements to tool reliability
- [Timeout Analysis](docs/timeout-analysis.md) - Detailed timeout implementation analysis

For the full documentation index, see [docs/index.md](docs/index.md).

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup
```bash
git clone https://github.com/haasonsaas/ocode.git
cd ocode

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code quality checks
black ocode_python/
isort ocode_python/
flake8 ocode_python/
mypy ocode_python/
```

## 📄 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

The AGPL-3.0 is a strong copyleft license that requires any modifications to be released under the same license. This ensures that the software remains free and open source, and that any improvements made to it are shared with the community.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) for local LLM infrastructure
- [Model Context Protocol](https://modelcontextprotocol.io) for tool integration standards
- The open-source AI and developer tools community

---

**Made with ❤️ for developers who want AI assistance without vendor lock-in.**
