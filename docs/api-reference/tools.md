# Tools API Reference

Complete API documentation for OCode's tool system.

## Agent Tools

### agent

Create, manage, and delegate tasks to specialized sub-agents.

```python
ToolDefinition(
    name="agent",
    description="Create, manage, and delegate tasks to specialized sub-agents",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform: 'create', 'list', 'delegate', 'status', 'results', 'terminate', 'queue'",
            required=True,
        ),
        ToolParameter(
            name="agent_type",
            type="string",
            description="Type of agent: 'coder', 'tester', 'reviewer', 'documenter', 'analyzer', 'fixer', 'researcher'",
            required=False,
        ),
        ToolParameter(
            name="agent_id",
            type="string",
            description="ID of specific agent to work with",
            required=False,
        ),
        ToolParameter(
            name="task_description",
            type="string",
            description="Description of task to delegate",
            required=False,
        ),
        ToolParameter(
            name="task_parameters",
            type="object",
            description="Parameters for the task",
            required=False,
            default={},
        ),
        ToolParameter(
            name="priority",
            type="string",
            description="Task priority: 'low', 'medium', 'high', 'urgent'",
            required=False,
            default="medium",
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Task timeout in seconds",
            required=False,
            default=300,
        ),
        ToolParameter(
            name="max_agents",
            type="number",
            description="Maximum number of agents to create",
            required=False,
            default=5,
        ),
    ],
)
```

## Analysis Tools

### architect

Analyze codebase architecture, dependencies, design patterns, and generate architectural insights.

```python
ToolDefinition(
    name="architect",
    description="Analyze codebase architecture, dependencies, design patterns, and generate architectural insights",
    parameters=[
        ToolParameter(
            name="analysis_type",
            type="string",
            description="Type of analysis: 'overview', 'dependencies', 'structure', 'patterns', 'metrics', 'health', 'diagram'",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path to analyze (file, directory, or project root)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="language",
            type="string",
            description="Programming language to focus on: 'python', 'javascript', 'typescript', 'java', 'auto'",
            required=False,
            default="auto",
        ),
        ToolParameter(
            name="depth",
            type="number",
            description="Analysis depth (1=surface, 3=deep)",
            required=False,
            default=2,
        ),
        ToolParameter(
            name="include_patterns",
            type="array",
            description="File patterns to include (e.g., ['*.py', '*.js'])",
            required=False,
        ),
        ToolParameter(
            name="exclude_patterns",
            type="array",
            description="File patterns to exclude (e.g., ['*test*', 'node_modules'])",
            required=False,
            default=[
                "*test*",
                "*__pycache__*",
                "node_modules",
                ".git",
                "venv",
                ".env",
            ],
        ),
        ToolParameter(
            name="output_format",
            type="string",
            description="Output format: 'summary', 'detailed', 'json', 'mermaid'",
            required=False,
            default="summary",
        ),
    ],
)
```

### think

Perform structured reasoning, analysis, and decision-making with various thinking frameworks.

```python
ToolDefinition(
    name="think",
    description="Perform structured reasoning, analysis, and decision-making with various thinking frameworks",
    parameters=[
        ToolParameter(
            name="thinking_type",
            type="string",
            description="Type of thinking: 'analyze', 'compare', 'pros_cons', 'root_cause', 'decision', 'brainstorm', 'breakdown', 'risk_assessment'",
            required=True,
        ),
        ToolParameter(
            name="topic",
            type="string",
            description="The main topic, problem, or question to think about",
            required=True,
        ),
        ToolParameter(
            name="context",
            type="string",
            description="Additional context, background information, or constraints",
            required=False,
        ),
        ToolParameter(
            name="options",
            type="array",
            description="List of options, alternatives, or solutions to evaluate (for comparison/decision types)",
            required=False,
        ),
        ToolParameter(
            name="criteria",
            type="array",
            description="Evaluation criteria or factors to consider",
            required=False,
        ),
        ToolParameter(
            name="save_to_memory",
            type="boolean",
            description="Save the thinking process to memory for later reference",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="output_format",
            type="string",
            description="Output format: 'structured', 'markdown', 'json'",
            required=False,
            default="structured",
        ),
    ],
)
```

## System Operations Tools

### bash

Execute shell commands with advanced features and safety controls.

```python
ToolDefinition(
    name="bash",
    description="Execute shell commands with advanced features and safety controls",
    category="System Operations",
    resource_locks=[ResourceLock.SHELL],
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="Shell command to execute",
            required=True,
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory for command execution",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Command timeout in seconds (0 = no timeout)",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="capture_output",
            type="boolean",
            description="Capture stdout and stderr",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="shell",
            type="string",
            description="Shell to use (bash, sh, zsh, fish)",
            required=False,
            default="bash",
        ),
        ToolParameter(
            name="env_vars",
            type="object",
            description="Additional environment variables",
            required=False,
            default={},
        ),
        ToolParameter(
            name="input_data",
            type="string",
            description="Input data to pipe to the command",
            required=False,
        ),
        ToolParameter(
            name="interactive",
            type="boolean",
            description="Run in interactive mode (for commands requiring input)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="safe_mode",
            type="boolean",
            description="Enable safety checks (prevent dangerous commands)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="show_command",
            type="boolean",
            description="Show the command being executed",
            required=False,
            default=True,
        ),
    ],
)
```

### script

Create and execute shell scripts with multiple commands.

```python
ToolDefinition(
    name="script",
    description="Create and execute shell scripts with multiple commands",
    category="System Operations",
    resource_locks=[ResourceLock.SHELL, ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="script_content",
            type="string",
            description="Script content (multiple commands separated by newlines)",
            required=True,
        ),
        ToolParameter(
            name="script_type",
            type="string",
            description="Script type: 'bash', 'sh', 'python', 'node'",
            required=False,
            default="bash",
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory for script execution",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Script timeout in seconds",
            required=False,
            default=60,
        ),
        ToolParameter(
            name="save_script",
            type="boolean",
            description="Save script to temporary file for inspection",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="env_vars",
            type="object",
            description="Environment variables for script",
            required=False,
            default={},
        ),
    ],
)
```

### curl

Make HTTP requests and download files.

```python
ToolDefinition(
    name="curl",
    description="Make HTTP requests and download files",
    resource_locks=[ResourceLock.NETWORK],
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="URL to request",
            required=True,
        ),
        ToolParameter(
            name="method",
            type="string",
            description="HTTP method (GET, POST, PUT, DELETE, etc.)",
            required=False,
            default="GET",
        ),
        ToolParameter(
            name="output_file",
            type="string",
            description="Save response to file (-o flag)",
            required=False,
        ),
        ToolParameter(
            name="headers",
            type="object",
            description="HTTP headers as key-value pairs",
            required=False,
        ),
        ToolParameter(
            name="data",
            type="string",
            description="Request body data",
            required=False,
        ),
        ToolParameter(
            name="json_data",
            type="object",
            description="JSON data to send (will set Content-Type: application/json)",
            required=False,
        ),
        ToolParameter(
            name="follow_redirects",
            type="boolean",
            description="Follow HTTP redirects (-L flag)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Request timeout in seconds",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="include_headers",
            type="boolean",
            description="Include response headers in output (-i flag)",
            required=False,
            default=False,
        ),
    ],
)
```

### env

Get, set, and manage environment variables.

```python
ToolDefinition(
    name="env",
    description="Get, set, and manage environment variables",
    category="System Operations",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action: get, set, unset, list, load, save",
            required=True,
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Environment variable name",
            required=False,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="Value to set",
            required=False,
        ),
        ToolParameter(
            name="file",
            type="string",
            description="Path to .env file (default: .env)",
            required=False,
            default=".env",
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Regex pattern to filter variables (for list action)",
            required=False,
        ),
        ToolParameter(
            name="export",
            type="boolean",
            description="Export variables to current process (for load action)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="Output format: text, json, export (default: text)",
            required=False,
            default="text",
        ),
    ],
)
```

### ping

Test network connectivity to a host using ping.

```python
ToolDefinition(
    name="ping",
    description="Test network connectivity to a host using ping",
    category="System Operations",
    parameters=[
        ToolParameter(
            name="host",
            type="string",
            description="Hostname or IP address to ping",
            required=True,
        ),
        ToolParameter(
            name="count",
            type="number",
            description="Number of ping packets to send (default: 4)",
            required=False,
            default=4,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Timeout in seconds for each ping (default: 5)",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="interval",
            type="number",
            description="Interval between pings in seconds (default: 1)",
            required=False,
            default=1,
        ),
    ],
)
```

### ps

Monitor and query system processes.

```python
ToolDefinition(
    name="ps",
    description="Monitor and query system processes",
    category="System Operations",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action: list, find, info, check",
            required=True,
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Process name to search for (supports partial match)",
            required=False,
        ),
        ToolParameter(
            name="pid",
            type="number",
            description="Process ID for 'info' action",
            required=False,
        ),
        ToolParameter(
            name="sort_by",
            type="string",
            description="Sort by: cpu, memory, pid, name (default: cpu)",
            required=False,
            default="cpu",
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Limit number of results (default: 20)",
            required=False,
            default=20,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="Output format: table, json (default: table)",
            required=False,
            default="table",
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Operation timeout in seconds (default: 10)",
            required=False,
            default=10,
        ),
    ],
)
```

### shell_command

Execute shell commands with interactive safety confirmation.

```python
ToolDefinition(
    name="shell_command",
    description="Execute shell commands with interactive safety confirmation",
    resource_locks=[ResourceLock.SHELL],
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="Shell command to execute",
            required=True,
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory for command (default: current)",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Command timeout in seconds (default: 30)",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="capture_output",
            type="boolean",
            description="Capture command output (default: true)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="confirmed",
            type="boolean",
            description="User has confirmed command execution (internal)",
            required=False,
            default=False,
        ),
    ],
)
```

### which

Locate executable programs in PATH.

```python
ToolDefinition(
    name="which",
    description="Locate executable programs in PATH",
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="Command name to locate",
            required=True,
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Show all matching executables in PATH (-a flag)",
            required=False,
            default=False,
        ),
    ],
)
```

### wc

Count lines, words, and characters in files.

```python
ToolDefinition(
    name="wc",
    description="Count lines, words, and characters in files",
    parameters=[
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file to analyze",
            required=True,
        ),
        ToolParameter(
            name="lines_only",
            type="boolean",
            description="Count lines only (-l flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="words_only",
            type="boolean",
            description="Count words only (-w flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="chars_only",
            type="boolean",
            description="Count characters only (-c flag)",
            required=False,
            default=False,
        ),
    ],
)
```

## Data Processing Tools

### json_yaml

Parse, query, and manipulate JSON/YAML data files or strings.

```python
ToolDefinition(
    name="json_yaml",
    description="Parse, query, and manipulate JSON/YAML data files or strings",
    category="Data Processing",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform: parse, query, set, validate",
            required=True,
        ),
        ToolParameter(
            name="source",
            type="string",
            description="File path or raw JSON/YAML string",
            required=True,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="Data format: json or yaml (auto-detect if not specified)",
            required=False,
            default="auto",
        ),
        ToolParameter(
            name="query",
            type="string",
            description="JSONPath query for 'query' action (e.g., '$.users[0].name')",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="JSONPath for 'set' action",
            required=False,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="Value to set (will be parsed as JSON)",
            required=False,
        ),
        ToolParameter(
            name="output_path",
            type="string",
            description="File path to write modified data",
            required=False,
        ),
        ToolParameter(
            name="pretty",
            type="boolean",
            description="Pretty print output (default: true)",
            required=False,
            default=True,
        ),
    ],
)
```

### sort

Sort lines in a file or text.

```python
ToolDefinition(
    name="sort",
    description="Sort lines in a file or text",
    parameters=[
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to file to sort (optional, can sort text directly)",
            required=False,
        ),
        ToolParameter(
            name="text",
            type="string",
            description="Text to sort (if no file_path provided)",
            required=False,
        ),
        ToolParameter(
            name="reverse",
            type="boolean",
            description="Sort in reverse order (-r flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="numeric",
            type="boolean",
            description="Sort numerically (-n flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="unique",
            type="boolean",
            description="Output only unique lines (-u flag)",
            required=False,
            default=False,
        ),
    ],
)
```

### uniq

Remove duplicate lines from sorted input.

```python
ToolDefinition(
    name="uniq",
    description="Remove duplicate lines from sorted input",
    parameters=[
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to file to process (optional, can process text directly)",
            required=False,
        ),
        ToolParameter(
            name="text",
            type="string",
            description="Text to process (if no file_path provided)",
            required=False,
        ),
        ToolParameter(
            name="count",
            type="boolean",
            description="Show count of occurrences (-c flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="duplicates_only",
            type="boolean",
            description="Show only duplicate lines (-d flag)",
            required=False,
            default=False,
        ),
    ],
)
```

## File Operations Tools

### file_read

Read the contents of a file.

```python
ToolDefinition(
    name="file_read",
    description="Read the contents of a file",
    category="File Operations",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="File encoding (default: utf-8)",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="offset",
            type="number",
            description="Start reading from this byte offset",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum number of bytes to read",
            required=False,
            default=-1,
        ),
    ],
)
```

### file_write

Write content to a file.

```python
ToolDefinition(
    name="file_write",
    description="Write content to a file",
    category="File Operations",
    resource_locks=[ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to write",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write to the file",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="File encoding (default: utf-8)",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="create_dirs",
            type="boolean",
            description="Create parent directories if they don't exist",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="append",
            type="boolean",
            description="Append to file instead of overwriting",
            required=False,
            default=False,
        ),
    ],
)
```

### file_list

List files and directories in a path.

```python
ToolDefinition(
    name="file_list",
    description="List files and directories in a path",
    category="File Operations",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to list (default: current directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="List files recursively",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="include_hidden",
            type="boolean",
            description="Include hidden files (starting with .)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="extensions",
            type="array",
            description="Filter by file extensions (e.g., ['.py', '.js'])",
            required=False,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern to filter files (e.g., '*.py', 'test_*')",
            required=False,
        ),
        ToolParameter(
            name="max_depth",
            type="number",
            description="Maximum directory depth for recursive listing",
            required=False,
            default=-1,
        ),
    ],
)
```

### file_search

Search for text patterns in files.

```python
ToolDefinition(
    name="file_search",
    description="Search for text patterns in files",
    category="File Operations",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="Text pattern to search for (supports regex)",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path to search in (default: current directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="extensions",
            type="array",
            description="File extensions to search in",
            required=False,
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Case sensitive search",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Maximum number of results to return",
            required=False,
            default=50,
        ),
        ToolParameter(
            name="context_lines",
            type="number",
            description="Number of context lines to show around matches",
            required=False,
            default=0,
        ),
    ],
)
```

### file_edit

Edit files in-place with find/replace, line operations, and transformations.

```python
ToolDefinition(
    name="file_edit",
    description="Edit files in-place with find/replace, line operations, and transformations",
    resource_locks=[ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to edit",
            required=True,
        ),
        ToolParameter(
            name="operation",
            type="string",
            description="Edit operation: 'replace', 'insert', 'delete', 'append', 'prepend'",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to insert/append/prepend (for insert/append/prepend operations)",
            required=False,
        ),
        ToolParameter(
            name="search_pattern",
            type="string",
            description="Pattern to search for (for replace/delete operations)",
            required=False,
        ),
        ToolParameter(
            name="replacement",
            type="string",
            description="Replacement text (for replace operation)",
            required=False,
        ),
        ToolParameter(
            name="line_number",
            type="number",
            description="Specific line number to operate on (1-based, for insert/delete)",
            required=False,
        ),
        ToolParameter(
            name="line_range",
            type="object",
            description='Line range {"start": 1, "end": 10} (for delete operation)',
            required=False,
        ),
        ToolParameter(
            name="regex",
            type="boolean",
            description="Treat search_pattern as regex",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Case-sensitive search",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="whole_word",
            type="boolean",
            description="Match whole words only",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="max_replacements",
            type="number",
            description="Maximum number of replacements (0 = unlimited)",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="backup",
            type="boolean",
            description="Create backup file before editing",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="dry_run",
            type="boolean",
            description="Show what would be changed without making changes",
            required=False,
            default=False,
        ),
    ],
)
```

### cp

Copy files or directories.

```python
ToolDefinition(
    name="cp",
    description="Copy files or directories",
    resource_locks=[ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="source",
            type="string",
            description="Source file or directory path",
            required=True,
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Destination file or directory path",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Copy directories recursively (-r flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="preserve",
            type="boolean",
            description="Preserve file metadata (timestamps, permissions)",
            required=False,
            default=True,
        ),
    ],
)
```

### mv

Move or rename files and directories.

```python
ToolDefinition(
    name="mv",
    description="Move or rename files and directories",
    resource_locks=[ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="source",
            type="string",
            description="Source file or directory path",
            required=True,
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Destination file or directory path",
            required=True,
        ),
    ],
)
```

### rm

Remove files and directories (with safety checks).

```python
ToolDefinition(
    name="rm",
    description="Remove files and directories (with safety checks)",
    resource_locks=[ResourceLock.FILESYSTEM_WRITE],
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to file or directory to remove",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Remove directories recursively (-r flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force removal without prompts (-f flag)",
            required=False,
            default=False,
        ),
    ],
)
```

### find

Find files and directories by name, size, type, etc.

```python
ToolDefinition(
    name="find",
    description="Find files and directories by name, size, type, etc.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to search in (default: current directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="name",
            type="string",
            description="File name pattern (supports wildcards)",
            required=False,
        ),
        ToolParameter(
            name="type",
            type="string",
            description="File type: 'f' for files, 'd' for directories",
            required=False,
        ),
        ToolParameter(
            name="maxdepth",
            type="number",
            description="Maximum directory depth to search",
            required=False,
        ),
        ToolParameter(
            name="size",
            type="string",
            description="File size filter (e.g., '+1M', '-100k')",
            required=False,
        ),
        ToolParameter(
            name="extension",
            type="string",
            description="File extension to search for (e.g., '.py', '.txt')",
            required=False,
        ),
    ],
)
```

### glob

Find files and directories using glob patterns.

```python
ToolDefinition(
    name="glob",
    description="Find files and directories using glob patterns",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern to match files (e.g., '*.py', '**/*.ts', 'src/**/*.{js,ts}')",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Base path to search from (default: current directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Enable recursive search (use ** in pattern for recursive)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="include_dirs",
            type="boolean",
            description="Include directories in results",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="include_hidden",
            type="boolean",
            description="Include hidden files and directories",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Maximum number of results to return",
            required=False,
            default=100,
        ),
    ],
)
```

### advanced_glob

Enhanced glob tool with additional filtering capabilities.

```python
ToolDefinition(
    name="advanced_glob",
    description="Enhanced glob tool with additional filtering capabilities",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern to match files (e.g., '*.py', '**/*.ts', 'src/**/*.{js,ts}')",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Base path to search from (default: current directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Enable recursive search (use ** in pattern for recursive)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="include_dirs",
            type="boolean",
            description="Include directories in results",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="include_hidden",
            type="boolean",
            description="Include hidden files and directories",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Maximum number of results to return",
            required=False,
            default=100,
        ),
        ToolParameter(
            name="exclude_patterns",
            type="array",
            description="Patterns to exclude from results (e.g., ['*.pyc', '__pycache__/*'])",
            required=False,
            default=[],
        ),
        ToolParameter(
            name="file_extensions",
            type="array",
            description="Filter by file extensions (e.g., ['.py', '.js', '.ts'])",
            required=False,
            default=[],
        ),
        ToolParameter(
            name="modified_since",
            type="string",
            description="ISO timestamp - only files modified since this time",
            required=False,
        ),
        ToolParameter(
            name="size_range",
            type="object",
            description="File size range filter (e.g., {'min': '1KB', 'max': '10MB'})",
            required=False,
        ),
    ],
)
```

### grep

Search for patterns in files using regular expressions.

```python
ToolDefinition(
    name="grep",
    description="Search for patterns in files using regular expressions",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="Search pattern (regex supported)",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path to search in (file or directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="file_pattern",
            type="string",
            description="File pattern to filter files (e.g., '*.py', '*.{js,ts}')",
            required=False,
            default="*",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Search recursively in subdirectories",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Case-sensitive search",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="whole_word",
            type="boolean",
            description="Match whole words only",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="invert_match",
            type="boolean",
            description="Show lines that don't match the pattern",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="context_lines",
            type="number",
            description="Number of context lines to show around matches",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="max_matches",
            type="number",
            description="Maximum number of matches to return",
            required=False,
            default=100,
        ),
        ToolParameter(
            name="include_line_numbers",
            type="boolean",
            description="Include line numbers in output",
            required=False,
            default=True,
        ),
    ],
)
```

### code_grep

Search for code patterns with language-aware features.

```python
ToolDefinition(
    name="code_grep",
    description="Search for code patterns with language-aware features",
    parameters=[
        ToolParameter(
            name="pattern",
            type="string",
            description="Search pattern (regex supported)",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path to search in (file or directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="file_pattern",
            type="string",
            description="File pattern to filter files (e.g., '*.py', '*.{js,ts}')",
            required=False,
            default="*",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Search recursively in subdirectories",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Case-sensitive search",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="whole_word",
            type="boolean",
            description="Match whole words only",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="invert_match",
            type="boolean",
            description="Show lines that don't match the pattern",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="context_lines",
            type="number",
            description="Number of context lines to show around matches",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="max_matches",
            type="number",
            description="Maximum number of matches to return",
            required=False,
            default=100,
        ),
        ToolParameter(
            name="include_line_numbers",
            type="boolean",
            description="Include line numbers in output",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="language",
            type="string",
            description="Programming language for syntax-aware search (python, javascript, etc.)",
            required=False,
        ),
        ToolParameter(
            name="search_type",
            type="string",
            description="Type of search: 'function', 'class', 'variable', 'import', 'comment', 'string'",
            required=False,
            default="text",
        ),
        ToolParameter(
            name="exclude_comments",
            type="boolean",
            description="Exclude matches in comments",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="exclude_strings",
            type="boolean",
            description="Exclude matches in string literals",
            required=False,
            default=False,
        ),
    ],
)
```

### head

Display the first lines of a file.

```python
ToolDefinition(
    name="head",
    description="Display the first lines of a file",
    parameters=[
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="lines",
            type="number",
            description="Number of lines to display (default: 10)",
            required=False,
            default=10,
        ),
    ],
)
```

### tail

Display the last lines of a file.

```python
ToolDefinition(
    name="tail",
    description="Display the last lines of a file",
    parameters=[
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="lines",
            type="number",
            description="Number of lines to display (default: 10)",
            required=False,
            default=10,
        ),
    ],
)
```

### ls

List directory contents with detailed information and filtering.

```python
ToolDefinition(
    name="ls",
    description="List directory contents with detailed information and filtering",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to list (file or directory)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="all",
            type="boolean",
            description="Show hidden files and directories (starting with .)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="long_format",
            type="boolean",
            description="Use long format showing permissions, size, dates, etc.",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="List contents recursively",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="sort_by",
            type="string",
            description="Sort by: 'name', 'size', 'modified', 'created', 'extension'",
            required=False,
            default="name",
        ),
        ToolParameter(
            name="reverse_sort",
            type="boolean",
            description="Reverse sort order",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="file_types",
            type="array",
            description="Filter by file types: ['file', 'dir', 'link', 'executable']",
            required=False,
            default=[],
        ),
        ToolParameter(
            name="extensions",
            type="array",
            description="Filter by file extensions (e.g., ['.py', '.js'])",
            required=False,
            default=[],
        ),
        ToolParameter(
            name="size_filter",
            type="object",
            description="Size filter: {'min': '1KB', 'max': '10MB'}",
            required=False,
        ),
        ToolParameter(
            name="max_depth",
            type="number",
            description="Maximum recursion depth (0 = unlimited)",
            required=False,
            default=0,
        ),
        ToolParameter(
            name="show_tree",
            type="boolean",
            description="Show as tree structure (only when recursive=True)",
            required=False,
            default=False,
        ),
    ],
)
```

## Git Operations Tools

### git_status

Get the current git repository status.

```python
ToolDefinition(
    name="git_status",
    description="Get the current git repository status",
    category="Git Operations",
    resource_locks=[ResourceLock.GIT],
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Repository path (default: current directory)",
            required=False,
            default=".",
        )
    ],
)
```

### git_commit

Create a git commit with specified message.

```python
ToolDefinition(
    name="git_commit",
    description="Create a git commit with specified message",
    resource_locks=[ResourceLock.GIT],
    parameters=[
        ToolParameter(
            name="message",
            type="string",
            description="Commit message",
            required=True,
        ),
        ToolParameter(
            name="files",
            type="array",
            description="Files to add to commit (default: all modified files)",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Repository path (default: current directory)",
            required=False,
            default=".",
        ),
    ],
)
```

### git_diff

Show git diff for files or commits.

```python
ToolDefinition(
    name="git_diff",
    description="Show git diff for files or commits",
    resource_locks=[ResourceLock.GIT],
    parameters=[
        ToolParameter(
            name="file",
            type="string",
            description="Specific file to show diff for",
            required=False,
        ),
        ToolParameter(
            name="staged",
            type="boolean",
            description="Show staged changes instead of working directory",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="commit",
            type="string",
            description="Compare against specific commit",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Repository path (default: current directory)",
            required=False,
            default=".",
        ),
    ],
)
```

### git_branch

Manage git branches.

```python
ToolDefinition(
    name="git_branch",
    description="Manage git branches",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action: 'list', 'create', 'checkout', 'delete'",
            required=True,
        ),
        ToolParameter(
            name="branch_name",
            type="string",
            description="Branch name (required for create/checkout/delete)",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Repository path (default: current directory)",
            required=False,
            default=".",
        ),
    ],
)
```

## MCP Tools

### mcp

Integrate with Model Context Protocol (MCP) servers for extended capabilities.

```python
ToolDefinition(
    name="mcp",
    description="Integrate with Model Context Protocol (MCP) servers for extended capabilities",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform: 'connect', 'list_servers', 'discover_tools', 'call_tool', 'get_resources', 'disconnect', 'status'",
            required=True,
        ),
        ToolParameter(
            name="server_name",
            type="string",
            description="Name of MCP server to connect to",
            required=False,
        ),
        ToolParameter(
            name="server_config",
            type="object",
            description="Server configuration (command, args, env)",
            required=False,
        ),
        ToolParameter(
            name="tool_name",
            type="string",
            description="Name of tool to call on MCP server",
            required=False,
        ),
        ToolParameter(
            name="tool_arguments",
            type="object",
            description="Arguments to pass to the MCP tool",
            required=False,
            default={},
        ),
        ToolParameter(
            name="resource_uri",
            type="string",
            description="URI of resource to fetch from MCP server",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Operation timeout in seconds",
            required=False,
            default=30,
        ),
    ],
)
```

## Memory Tools

### memory_read

Read session memory, context, and persistent data.

```python
ToolDefinition(
    name="memory_read",
    description="Read session memory, context data, and persistent information from various sources",
    parameters=[
        ToolParameter(
            name="memory_type",
            type="string",
            description="Type of memory to read: 'session', 'context', 'persistent', 'all'",
            required=True,
        ),
        ToolParameter(
            name="key",
            type="string",
            description="Specific key to read (exact match, e.g. 'project_config', 'address'). Leave empty to read all entries.",
            required=False,
        ),
        ToolParameter(
            name="category",
            type="string",
            description="Category to filter by (e.g., 'variables', 'files', 'tasks', 'notes')",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Specific session ID to read from",
            required=False,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="Output format: 'summary', 'detailed', 'raw'",
            required=False,
            default="summary",
        ),
        ToolParameter(
            name="max_entries",
            type="number",
            description="Maximum number of entries to return",
            required=False,
            default=50,
        ),
    ],
)
```

### memory_write

Write and manage session memory, context, and persistent data.

```python
ToolDefinition(
    name="memory_write",
    description="Write and manage session memory, context data, and persistent information",
    resource_locks=[ResourceLock.MEMORY],
    parameters=[
        ToolParameter(
            name="memory_type",
            type="string",
            description="Type of memory to write: 'session', 'context', 'persistent'",
            required=True,
        ),
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: 'set', 'update', 'delete', 'clear', 'append', 'lobotomize'",
            required=True,
        ),
        ToolParameter(
            name="key",
            type="string",
            description="Key/name for the data",
            required=False,
        ),
        ToolParameter(
            name="value",
            type="object",
            description="Data to store (any JSON-serializable value)",
            required=False,
        ),
        ToolParameter(
            name="category",
            type="string",
            description="Category for organization (e.g., 'variables', 'files', 'tasks', 'notes')",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Session ID (auto-generated if not provided for session memory)",
            required=False,
        ),
        ToolParameter(
            name="metadata",
            type="object",
            description="Additional metadata to store with the entry",
            required=False,
        ),
    ],
)
```

## Notebook Tools

### notebook_read

Read and analyze Jupyter notebook files (.ipynb), extracting cells, outputs, and metadata.

```python
ToolDefinition(
    name="notebook_read",
    description="Read and analyze Jupyter notebook files (.ipynb), extracting cells, outputs, and metadata",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the notebook file",
            required=True,
        ),
        ToolParameter(
            name="include_outputs",
            type="boolean",
            description="Include cell outputs in the result",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="include_metadata",
            type="boolean",
            description="Include notebook and cell metadata",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="cell_types",
            type="array",
            description="Filter by cell types (code, markdown, raw)",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="cell_range",
            type="string",
            description="Cell range to read (e.g., '1 - 5' or '3,5,7')",
            required=False,
            default=None,
        ),
    ],
)
```

### notebook_edit

Edit Jupyter notebook files by modifying, adding, or removing cells.

```python
ToolDefinition(
    name="notebook_edit",
    description="Edit Jupyter notebook files by modifying, adding, or removing cells",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the notebook file",
            required=True,
        ),
        ToolParameter(
            name="operation",
            type="string",
            description="Operation to perform: 'update_cell', 'add_cell', 'remove_cell', 'clear_outputs', 'set_metadata'",
            required=True,
        ),
        ToolParameter(
            name="cell_index",
            type="number",
            description="Index of the cell to modify (0-based)",
            required=False,
        ),
        ToolParameter(
            name="cell_type",
            type="string",
            description="Type of cell: 'code', 'markdown', or 'raw'",
            required=False,
            default="code",
        ),
        ToolParameter(
            name="source",
            type="string",
            description="New source code/content for the cell",
            required=False,
        ),
        ToolParameter(
            name="metadata",
            type="object",
            description="Metadata to set (for set_metadata operation)",
            required=False,
        ),
        ToolParameter(
            name="backup",
            type="boolean",
            description="Create backup before editing",
            required=False,
            default=True,
        ),
    ],
)
```

## Search Tools

### web_search

Search the web for current information to enhance responses with real-time data.

```python
ToolDefinition(
    name="web_search",
    description="Search the web for current information to enhance responses with real-time data",
    category="Search",
    resource_locks=[ResourceLock.NETWORK],
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="The search query to execute",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            type="number",
            description="Maximum number of results to return",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="include_snippets",
            type="boolean",
            description="Whether to include content snippets",
            required=False,
            default=True,
        ),
    ],
)
```

## Session Management Tools

### session_manager

Manage conversation sessions and checkpoints - save, load, resume, and branch conversations.

```python
ToolDefinition(
    name="session_manager",
    description="Manage conversation sessions and checkpoints - save, load, resume, and branch conversations",
    category="Session Management",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="The session management action to perform",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Session ID for load/delete/export operations",
            required=False,
        ),
        ToolParameter(
            name="checkpoint_id",
            type="string",
            description="Checkpoint ID for checkpoint operations",
            required=False,
        ),
        ToolParameter(
            name="description",
            type="string",
            description="Description for checkpoints or sessions",
            required=False,
        ),
        ToolParameter(
            name="tags",
            type="array",
            description="Tags for categorizing checkpoints",
            required=False,
        ),
        ToolParameter(
            name="output_file",
            type="string",
            description="Output file path for exports",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Limit number of results",
            required=False,
            default=20,
        ),
        ToolParameter(
            name="days",
            type="number",
            description="Number of days for cleanup operations",
            required=False,
            default=30,
        ),
    ],
)
```

## Sticker Tools

### sticker

Create, manage, and organize code annotations, notes, and markers.

```python
ToolDefinition(
    name="sticker",
    description="Create, manage, and organize code annotations, notes, TODOs, and markers",
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="Action to perform: 'add', 'list', 'search', 'update', 'resolve', 'delete', 'export', 'import', 'stats'",
            required=True,
        ),
        ToolParameter(
            name="sticker_type",
            type="string",
            description="Type of sticker: 'note', 'todo', 'fixme', 'warning', 'info', 'bookmark', 'question'",
            required=False,
            default="note",
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file to annotate",
            required=False,
        ),
        ToolParameter(
            name="line_number",
            type="number",
            description="Line number in the file (1-based)",
            required=False,
        ),
        ToolParameter(
            name="column_number",
            type="number",
            description="Column number in the line (1-based)",
            required=False,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content of the annotation/note",
            required=False,
        ),
        ToolParameter(
            name="priority",
            type="string",
            description="Priority level: 'low', 'medium', 'high', 'urgent'",
            required=False,
            default="medium",
        ),
        ToolParameter(
            name="tags",
            type="array",
            description="Tags to categorize the sticker",
            required=False,
            default=[],
        ),
        ToolParameter(
            name="sticker_id",
            type="string",
            description="ID of specific sticker to work with",
            required=False,
        ),
        ToolParameter(
            name="search_query",
            type="string",
            description="Search query for finding stickers",
            required=False,
        ),
        ToolParameter(
            name="filter_by",
            type="object",
            description="Filters for listing stickers (type, priority, tags, resolved, file)",
            required=False,
            default={},
        ),
        ToolParameter(
            name="export_format",
            type="string",
            description="Export format: 'json', 'markdown', 'csv', 'html'",
            required=False,
            default="json",
        ),
    ],
)
```

## Testing Tools

### test_runner

Run tests in the project.

```python
ToolDefinition(
    name="test_runner",
    description="Run tests in the project",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to test directory or file",
            required=False,
        ),
        ToolParameter(
            name="framework",
            type="string",
            description="Test framework to use (pytest, unittest)",
            required=False,
        ),
        ToolParameter(
            name="verbose",
            type="boolean",
            description="Enable verbose output",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Test execution timeout in seconds",
            required=False,
            default=300,
        ),
    ],
)
```

### lint

Run code linters and formatters.

```python
ToolDefinition(
    name="lint",
    description="Run code linters and formatters",
    parameters=[
        ToolParameter(
            name="tool",
            type="string",
            description="Linting tool: 'flake8', 'black', 'eslint', 'prettier', 'auto'",
            required=False,
            default="auto",
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Path to code files or directory",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="fix",
            type="boolean",
            description="Automatically fix issues when possible",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="config",
            type="string",
            description="Config file path",
            required=False,
        ),
    ],
)
```

### coverage

Measure and report test coverage.

```python
ToolDefinition(
    name="coverage",
    description="Measure and report test coverage",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to source code",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="format",
            type="string",
            description="Report format: 'text', 'html', 'xml'",
            required=False,
            default="text",
        ),
        ToolParameter(
            name="min_coverage",
            type="number",
            description="Minimum coverage percentage required",
            required=False,
            default=80,
        ),
    ],
)
```