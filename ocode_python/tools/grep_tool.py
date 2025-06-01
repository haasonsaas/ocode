"""
Advanced text and code searching tool with regex support.
Enhanced with ripgrep integration, parallel processing, and better pattern matching.
"""

import ast
import asyncio
import collections
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Pattern, Tuple

from .base import Tool, ToolDefinition, ToolParameter, ToolResult


class GrepTool(Tool):
    """Tool for advanced text and code searching with regex support."""

    def __init__(self, config=None):
        super().__init__()
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit for memory-safe operation
        self.max_matches_per_file = 1000  # Limit matches to prevent memory explosion
        self.has_ripgrep = shutil.which("rg") is not None

        # Use config if provided
        if config:
            self.use_ripgrep = self.has_ripgrep and config.get("use_ripgrep", True)
            self.parallel_workers = config.get("parallel_grep_workers", 4)
        else:
            self.use_ripgrep = self.has_ripgrep  # Default to using if available
            self.parallel_workers = 4

    @property
    def definition(self) -> ToolDefinition:
        """Define the grep tool specification.

        Returns:
            ToolDefinition with parameters for advanced text searching including
            regex patterns, file filtering, case sensitivity, context lines,
            and support for ripgrep optimization when available.
        """
        return ToolDefinition(
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
                    description="File pattern to filter files (e.g., '*.py', '*.{js,ts}')",  # noqa: E501
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute text search."""
        try:
            pattern = kwargs.get("pattern")
            if not pattern:
                return ToolResult(
                    success=False, output="", error="Pattern parameter is required"
                )
            path = kwargs.get("path", ".")
            file_pattern = kwargs.get("file_pattern", "*")
            recursive = kwargs.get("recursive", True)
            case_sensitive = kwargs.get("case_sensitive", True)
            whole_word = kwargs.get("whole_word", False)
            invert_match = kwargs.get("invert_match", False)
            context_lines = kwargs.get("context_lines", 0)
            max_matches = kwargs.get("max_matches", 100)
            include_line_numbers = kwargs.get("include_line_numbers", True)

            search_path = Path(path).resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Search path does not exist: {path}",
                )

            # Compile regex pattern
            regex_flags = 0 if case_sensitive else re.IGNORECASE

            if whole_word:
                pattern = rf"\b{str(pattern)}\b"

            try:
                compiled_pattern: Pattern[str] = re.compile(str(pattern), regex_flags)
            except re.error as e:
                return ToolResult(
                    success=False, output="", error=f"Invalid regex pattern: {str(e)}"
                )

            # Try ripgrep first if available
            if self.use_ripgrep and self.has_ripgrep:
                success, rg_matches, rg_files = await self._search_with_ripgrep(
                    pattern=str(pattern),
                    search_path=search_path,
                    file_pattern=file_pattern,
                    recursive=recursive,
                    case_sensitive=case_sensitive,
                    whole_word=whole_word,
                    invert_match=invert_match,
                    context_lines=context_lines,
                    max_matches=max_matches,
                )

                if success:
                    all_matches = rg_matches
                    files_searched = rg_files
                else:
                    # Fall back to Python implementation
                    files_to_search = []
                    if search_path.is_file():
                        files_to_search = [search_path]
                    else:
                        files_to_search = self._find_files(
                            search_path, file_pattern, recursive
                        )

                    # Use parallel processing for multiple files
                    if len(files_to_search) > 1:
                        all_matches, files_searched = await self._search_files_parallel(
                            files_to_search,
                            compiled_pattern,
                            invert_match,
                            context_lines,
                            include_line_numbers,
                            max_matches,
                        )
                    else:
                        # Single file, process normally
                        all_matches = []
                        files_searched = 0
                        for file_path in files_to_search:
                            try:
                                matches = await self._search_file(
                                    file_path,
                                    compiled_pattern,
                                    invert_match,
                                    context_lines,
                                    include_line_numbers,
                                )
                                if matches:
                                    all_matches.extend(matches)
                                files_searched += 1
                                if len(all_matches) >= max_matches:
                                    all_matches = all_matches[:max_matches]
                                    break
                            except Exception:  # nosec
                                continue
            else:
                # Python implementation
                files_to_search = []
                if search_path.is_file():
                    files_to_search = [search_path]
                else:
                    files_to_search = self._find_files(
                        search_path, file_pattern, recursive
                    )

                # Use parallel processing for multiple files
                if len(files_to_search) > 1:
                    all_matches, files_searched = await self._search_files_parallel(
                        files_to_search,
                        compiled_pattern,
                        invert_match,
                        context_lines,
                        include_line_numbers,
                        max_matches,
                    )
                else:
                    # Single file, process normally
                    all_matches = []
                    files_searched = 0
                    for file_path in files_to_search:
                        try:
                            matches = await self._search_file(
                                file_path,
                                compiled_pattern,
                                invert_match,
                                context_lines,
                                include_line_numbers,
                            )
                            if matches:
                                all_matches.extend(matches)
                            files_searched += 1
                            if len(all_matches) >= max_matches:
                                all_matches = all_matches[:max_matches]
                                break
                        except Exception:  # nosec
                            continue

            # Format output
            if not all_matches:
                output = f"No matches found for pattern: {pattern}"
            else:
                output_lines = [
                    f"Found {len(all_matches)} matches in {files_searched} files:",
                    "",
                ]

                current_file = None
                for match in all_matches:
                    if match["file"] != current_file:
                        current_file = match["file"]
                        relative_path = Path(current_file).relative_to(
                            search_path.parent if search_path.is_file() else search_path
                        )
                        output_lines.append(f"📄 {relative_path}:")

                    if include_line_numbers:
                        output_lines.append(
                            f"  {match['line_num']:4d}: {match['text']}"
                        )
                    else:
                        output_lines.append(f"  {match['text']}")

                    # Add context lines if any
                    for context in match.get("context", []):
                        if include_line_numbers:
                            output_lines.append(
                                f"  {context['line_num']:4d}| {context['text']}"
                            )
                        else:
                            output_lines.append(f"      | {context['text']}")

                if len(all_matches) >= max_matches:
                    output_lines.append(f"\n... truncated at {max_matches} matches")

                output = "\n".join(output_lines)

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pattern": pattern,
                    "matches_found": len(all_matches),
                    "files_searched": files_searched,
                    "search_path": str(search_path),
                    "matches": all_matches[:50],  # Limit metadata size
                },
            )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Search failed: {str(e)}"
            )

    async def _search_with_ripgrep(
        self,
        pattern: str,
        search_path: Path,
        file_pattern: str = "*",
        recursive: bool = True,
        case_sensitive: bool = True,
        whole_word: bool = False,
        invert_match: bool = False,
        context_lines: int = 0,
        max_matches: int = 100,
    ) -> Tuple[bool, List[Dict[str, Any]], int]:
        """Use ripgrep for fast searching when available."""
        rg_cmd = ["rg", "--json", "--no-heading", "--with-filename", "--line-number"]

        # Add flags
        if not case_sensitive:
            rg_cmd.append("-i")
        if whole_word:
            rg_cmd.append("-w")
        if invert_match:
            rg_cmd.append("-v")
        if context_lines > 0:
            rg_cmd.extend(["-C", str(context_lines)])
        if max_matches:
            rg_cmd.extend(["-m", str(max_matches)])

        # Add file pattern
        if file_pattern and file_pattern != "*":
            # Handle brace expansion patterns
            patterns = self._parse_file_pattern(file_pattern)
            for p in patterns:
                rg_cmd.extend(["-g", p])

        # Add pattern and path
        rg_cmd.extend([pattern, str(search_path)])

        # If not recursive, add --max-depth 1
        if not recursive:
            rg_cmd.extend(["--max-depth", "1"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *rg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode not in (0, 1):  # 0 = found, 1 = not found
                return False, [], 0

            # Parse ripgrep JSON output
            matches = []
            files_seen = set()

            for line in stdout.decode().splitlines():
                try:
                    data = json.loads(line)
                    if data["type"] == "match":
                        match_data = data["data"]
                        file_path = match_data["path"]["text"]
                        files_seen.add(file_path)

                        match_info = {
                            "file": file_path,
                            "line_num": match_data["line_number"],
                            "text": match_data["lines"]["text"].rstrip(),
                            "context": [],
                        }

                        # Handle context lines if present
                        if "context" in data:
                            for ctx in data["context"]:
                                context = match_info.get("context", [])
                                if isinstance(context, list):
                                    context.append(
                                        {
                                            "line_num": ctx["line_number"],
                                            "text": ctx["lines"]["text"].rstrip(),
                                            "type": ctx["type"],  # "before" or "after"
                                        }
                                    )

                        matches.append(match_info)

                except json.JSONDecodeError:
                    continue

            return True, matches, len(files_seen)

        except Exception:
            # Fall back to Python implementation
            return False, [], 0

    def _is_binary_file(self, file_path: Path, sample_size: int = 8192) -> bool:
        """Check if file is binary to skip it."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(sample_size)
                # Check for null bytes
                if b"\x00" in chunk:
                    return True
                # Check if mostly non-text characters
                text_chars = set(range(32, 127)) | {9, 10, 13}
                non_text = sum(1 for b in chunk if b not in text_chars)
                return non_text / len(chunk) > 0.3 if chunk else False
        except Exception:
            return True

    async def _search_files_parallel(
        self,
        files: List[Path],
        pattern: Pattern[str],
        invert_match: bool,
        context_lines: int,
        include_line_numbers: bool,
        max_matches: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search multiple files in parallel for better performance."""
        semaphore = asyncio.Semaphore(self.parallel_workers)
        all_matches = []
        files_searched = 0

        async def search_with_limit(file_path: Path):
            async with semaphore:
                try:
                    matches = await self._search_file(
                        file_path,
                        pattern,
                        invert_match,
                        context_lines,
                        include_line_numbers,
                    )
                    return matches, True
                except Exception:
                    return [], False

        # Create tasks for all files
        tasks = [asyncio.create_task(search_with_limit(f)) for f in files]

        # Process results as they complete
        for coro in asyncio.as_completed(tasks):
            matches, success = await coro
            if success:
                files_searched += 1
            if matches:
                all_matches.extend(matches)
                # Check if we've hit the max matches limit
                if len(all_matches) >= max_matches:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    all_matches = all_matches[:max_matches]
                    break

        return all_matches, files_searched

    def _parse_file_pattern(self, pattern: str) -> List[str]:
        """Parse file patterns supporting {ext1,ext2} syntax."""
        if "{" in pattern and "}" in pattern:
            import re

            match = re.match(r"(.*)\{([^}]+)\}(.*)", pattern)
            if match:
                prefix, extensions, suffix = match.groups()
                return [f"{prefix}{ext}{suffix}" for ext in extensions.split(",")]
        return [pattern]

    def _find_files(
        self, base_path: Path, file_pattern: str, recursive: bool
    ) -> List[Path]:
        """Find files matching the pattern with enhanced pattern support."""
        import fnmatch

        # Parse patterns (handles brace expansion)
        patterns = self._parse_file_pattern(file_pattern)
        files = set()

        for pattern in patterns:
            if recursive:
                for file_path in base_path.rglob("*"):
                    if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                        files.add(file_path)
            else:
                for file_path in base_path.iterdir():
                    if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                        files.add(file_path)

        return sorted(files)

    async def _search_file(
        self,
        file_path: Path,
        pattern: Pattern[str],
        invert_match: bool,
        context_lines: int,
        include_line_numbers: bool,
    ) -> List[Dict[str, Any]]:
        """Search for pattern in a single file."""

        try:
            # Check file size before processing
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return [
                    {
                        "file": str(file_path),
                        "line_num": 0,
                        "text": f"File too large ({file_size} bytes, max: {self.max_file_size})",  # noqa: E501
                        "context": [],
                    }
                ]

            # Check if file is binary
            if self._is_binary_file(file_path):
                return []  # Skip binary files silently

            # Use streaming approach for memory efficiency
            return await self._search_file_streaming(
                file_path, pattern, invert_match, context_lines, include_line_numbers
            )

        except Exception as e:
            return [
                {
                    "file": str(file_path),
                    "line_num": 0,
                    "text": f"Error reading file: {str(e)}",
                    "context": [],
                }
            ]

    async def _search_file_streaming(
        self,
        file_path: Path,
        pattern: Pattern[str],
        invert_match: bool,
        context_lines: int,
        include_line_numbers: bool,
    ) -> List[Dict[str, Any]]:
        """Stream-based file search with context line support."""
        matches: List[Dict[str, Any]] = []

        try:
            if context_lines > 0:
                # Use sliding window for context
                context_buffer: collections.deque = collections.deque(
                    maxlen=context_lines
                )
                pending_context = []

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if len(matches) >= self.max_matches_per_file:
                            break  # Prevent memory explosion

                        line_stripped = line.rstrip("\n\r")
                        found_match = bool(pattern.search(line_stripped))

                        if found_match != invert_match:  # XOR logic for invert_match
                            match_info = {
                                "file": str(file_path),
                                "line_num": line_num,
                                "text": line_stripped,
                                "context": [],
                            }

                            # Add before context
                            for ctx_line_num, ctx_text in context_buffer:
                                context = match_info.get("context", [])
                                if isinstance(context, list):
                                    context.append(
                                        {
                                            "line_num": ctx_line_num,
                                            "text": ctx_text,
                                            "type": "before",
                                        }
                                    )

                            matches.append(match_info)
                            pending_context = [match_info]  # Track for after context

                        else:
                            # Add to pending after context if within range
                            if pending_context:
                                for match in pending_context[:]:
                                    if isinstance(match, dict) and "line_num" in match:
                                        match_line_num = match.get("line_num", 0)
                                        if (
                                            isinstance(match_line_num, int)
                                            and line_num - match_line_num
                                            <= context_lines
                                        ):
                                            match_context = match.get("context", [])
                                            if isinstance(match_context, list):
                                                match_context.append(
                                                    {
                                                        "line_num": line_num,
                                                        "text": line_stripped,
                                                        "type": "after",
                                                    }
                                                )
                                    else:
                                        pending_context.remove(match)

                            # Update context buffer
                            context_buffer.append((line_num, line_stripped))
            else:
                # No context lines needed, simpler logic
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if len(matches) >= self.max_matches_per_file:
                            break  # Prevent memory explosion

                        line_stripped = line.rstrip("\n\r")
                        found_match = bool(pattern.search(line_stripped))

                        if found_match != invert_match:  # XOR logic for invert_match
                            match_info = {
                                "file": str(file_path),
                                "line_num": line_num,
                                "text": line_stripped,
                                "context": [],
                            }
                            matches.append(match_info)

            return matches
        except Exception:
            return matches


class CodeGrepTool(GrepTool):
    """Enhanced grep tool specifically designed for code searching."""

    def __init__(self, config=None):
        super().__init__(config)
        self._comment_patterns = {
            "python": (r"#.*$", r'""".*?"""', r"'''.*?'''"),
            "javascript": (r"//.*$", r"/\*.*?\*/"),
            "typescript": (r"//.*$", r"/\*.*?\*/"),
        }
        self._string_patterns = {
            "python": (r'""".*?"""', r"'''.*?'''", r'".*?"', r"'.*?'"),
            "javascript": (r'".*?"', r"'.*?'", r"`.*?`"),
            "typescript": (r'".*?"', r"'.*?'", r"`.*?`"),
        }

    @property
    def definition(self) -> ToolDefinition:
        base_def = super().definition
        base_def.name = "code_grep"
        base_def.description = "Search for code patterns with language-aware features"
        base_def.parameters.extend(
            [
                ToolParameter(
                    name="language",
                    type="string",
                    description="Programming language for syntax-aware search (python, javascript, etc.)",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="search_type",
                    type="string",
                    description="Type of search: 'function', 'class', 'variable', 'import', 'comment', 'string'",  # noqa: E501
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
            ]
        )
        return base_def

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute code-aware search."""

        # Extract parameters
        pattern = kwargs.get("pattern")
        path = kwargs.get("path", ".")
        file_pattern = kwargs.get("file_pattern", "*")
        recursive = kwargs.get("recursive", True)
        case_sensitive = kwargs.get("case_sensitive", True)
        whole_word = kwargs.get("whole_word", False)
        invert_match = kwargs.get("invert_match", False)
        context_lines = kwargs.get("context_lines", 0)
        max_matches = kwargs.get("max_matches", 100)
        include_line_numbers = kwargs.get("include_line_numbers", True)
        language = kwargs.get("language")
        search_type = kwargs.get("search_type", "text")
        exclude_comments = kwargs.get("exclude_comments", False)
        exclude_strings = kwargs.get("exclude_strings", False)

        # Enhanced language-specific parsing
        if search_type != "text":
            # Create language-specific patterns
            if search_type == "function":
                if language == "python":
                    pattern = rf"(?:def|async\s+def)\s+{pattern}\s*\("
                elif language in ["javascript", "typescript"]:
                    pattern = rf"(?:function\s+{pattern}\s*\(|const\s+{pattern}\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)|{pattern}\s*:\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))"  # noqa: E501
                elif language == "java":
                    pattern = rf"(?:public|private|protected|static|\s)+\w+\s+{pattern}\s*\("  # noqa: E501
                elif language == "go":
                    pattern = rf"func\s+(?:\([^)]+\)\s+)?{pattern}\s*\("
                elif language == "rust":
                    pattern = rf"fn\s+{pattern}\s*[<(]"
            elif search_type == "class":
                if language == "python":
                    pattern = rf"class\s+{pattern}\s*[\(:]"
                elif language in ["javascript", "typescript"]:
                    pattern = rf"class\s+{pattern}\s*(?:extends\s+\w+\s*)?[{{\s]"
                elif language == "java":
                    pattern = rf"(?:public\s+)?class\s+{pattern}\s*(?:extends\s+\w+\s*)?(?:implements\s+[\w,\s]+\s*)?{{"  # noqa: E501
                elif language == "go":
                    pattern = rf"type\s+{pattern}\s+struct\s*\{{"
                elif language == "rust":
                    pattern = rf"(?:pub\s+)?struct\s+{pattern}\s*[{{<]"
            elif search_type == "import":
                if language == "python":
                    pattern = rf"(?:import\s+{pattern}|from\s+{pattern}\s+import|from\s+\S+\s+import.*{pattern})"  # noqa: E501
                elif language in ["javascript", "typescript"]:
                    pattern = rf"(?:import.*from\s+['\"].*{pattern}.*['\"]|import\s+.*{pattern}|require\(['\"].*{pattern}.*['\"]\\))"  # noqa: E501
                elif language == "java":
                    pattern = rf"import\s+(?:static\s+)?.*{pattern}"
                elif language == "go":
                    pattern = rf"import\s+(?:\(.*{pattern}.*\)|['\"].*{pattern}.*['\"])"
                elif language == "rust":
                    pattern = rf"use\s+.*{pattern}"
            elif search_type == "variable":
                if language == "python":
                    pattern = rf"(?:{pattern}\s*=|self\.{pattern}\s*=)"
                elif language in ["javascript", "typescript"]:
                    pattern = rf"(?:(?:let|const|var)\s+{pattern}\s*[=;]|this\.{pattern}\s*=)"  # noqa: E501
                elif language == "java":
                    pattern = rf"(?:(?:public|private|protected|static|final|\s)+)?\w+\s+{pattern}\s*[=;]"  # noqa: E501
                elif language == "go":
                    pattern = rf"(?:{pattern}\s*:=|var\s+{pattern}\s+)"
                elif language == "rust":
                    pattern = rf"(?:let\s+(?:mut\s+)?{pattern}\s*[=;])"
            elif search_type == "comment":
                if language == "python":
                    pattern = f"#.*{pattern}"
                elif language in ["javascript", "typescript", "java", "go", "rust"]:
                    pattern = rf"(?://.*{pattern}|/\*.*{pattern}.*\*/)"
            elif search_type == "string":
                if language == "python":
                    pattern = f"(?:['\"].*{pattern}.*['\"]|['\"]['\"]['\"].*{pattern}.*['\"]['\"]['\"])"  # noqa: E501
                elif language in ["javascript", "typescript"]:
                    pattern = f"(?:['\"].*{pattern}.*['\"]|`.*{pattern}.*`)"
                else:
                    pattern = f"['\"].*{pattern}.*['\"]"

        # Use enhanced search if we have language info
        if language or exclude_comments or exclude_strings:
            return await self._enhanced_search(
                pattern=pattern,
                path=path,
                file_pattern=file_pattern,
                recursive=recursive,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
                invert_match=invert_match,
                context_lines=context_lines,
                max_matches=max_matches,
                include_line_numbers=include_line_numbers,
                language=language,
                exclude_comments=exclude_comments,
                exclude_strings=exclude_strings,
            )
        else:
            # Fall back to parent implementation
            return await super().execute(
                pattern=pattern,
                path=path,
                file_pattern=file_pattern,
                recursive=recursive,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
                invert_match=invert_match,
                context_lines=context_lines,
                max_matches=max_matches,
                include_line_numbers=include_line_numbers,
            )

    async def _search_file(
        self,
        file_path: Path,
        pattern: Pattern[str],
        invert_match: bool,
        context_lines: int,
        include_line_numbers: bool,
        exclude_comments: bool = False,
        exclude_strings: bool = False,
    ) -> List[Dict[str, Any]]:
        """Enhanced file search with language-specific parsing."""
        matches: List[Dict[str, Any]] = []

        try:
            # Check file size before processing
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return [
                    {
                        "file": str(file_path),
                        "line_num": 0,
                        "text": f"File too large ({file_size} bytes, max: {self.max_file_size}) - skipping AST parsing",  # noqa: E501
                        "context": [],
                    }
                ]

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            return matches

        # Determine language from file extension
        ext = file_path.suffix.lower()
        if ext == ".py":
            language = "python"
        elif ext in [".js", ".jsx"]:
            language = "javascript"
        elif ext in [".ts", ".tsx"]:
            language = "typescript"
        else:
            # Fall back to basic search for unknown languages
            return await super()._search_file(
                file_path, pattern, invert_match, context_lines, include_line_numbers
            )

        # Parse code based on language
        if language == "python":
            try:
                tree = ast.parse(content)
                # Get line ranges for different code elements
                comment_ranges = self._get_python_comment_ranges(content)
                string_ranges = self._get_python_string_ranges(tree)

                # Search through lines with context
                for i, line in enumerate(lines):
                    line_stripped = line.rstrip("\n\r")

                    # Skip if line is in a comment or string if requested
                    if (
                        exclude_comments
                        and self._is_in_range(i + 1, comment_ranges)
                        or exclude_strings
                        and self._is_in_range(i + 1, string_ranges)
                    ):
                        continue

                    found_match = bool(pattern.search(line_stripped))
                    if found_match != invert_match:
                        match_info = self._create_match_info(
                            file_path,
                            i,
                            line_stripped,
                            lines,
                            context_lines,
                            include_line_numbers,
                        )
                        matches.append(match_info)

            except SyntaxError:
                # Fall back to basic search if parsing fails
                return await super()._search_file(
                    file_path,
                    pattern,
                    invert_match,
                    context_lines,
                    include_line_numbers,
                )

        else:  # JavaScript/TypeScript
            # Basic JS/TS parsing using regex
            comment_ranges = self._get_js_comment_ranges(content)
            string_ranges = self._get_js_string_ranges(content)

            for i, line in enumerate(lines):
                line_stripped = line.rstrip("\n\r")

                # Skip if line is in a comment or string if requested
                if (
                    exclude_comments
                    and self._is_in_range(i + 1, comment_ranges)
                    or exclude_strings
                    and self._is_in_range(i + 1, string_ranges)
                ):
                    continue

                found_match = bool(pattern.search(line_stripped))
                if found_match != invert_match:
                    match_info = self._create_match_info(
                        file_path,
                        i,
                        line_stripped,
                        lines,
                        context_lines,
                        include_line_numbers,
                    )
                    matches.append(match_info)

        return matches

    def _get_python_comment_ranges(self, content: str) -> List[tuple]:
        """Get line ranges for Python comments.

        Args:
            content: The full content of the Python file.

        Returns:
            List of tuples containing (start_line, end_line) for each comment.
        """
        ranges = []
        for pattern in self._comment_patterns["python"]:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                start_line = content[: match.start()].count("\n") + 1
                end_line = content[: match.end()].count("\n") + 1
                ranges.append((start_line, end_line))
        return ranges

    def _get_python_string_ranges(self, tree: ast.AST) -> List[tuple]:
        """Get line ranges for Python string literals.

        Args:
            tree: The AST tree of the Python file.

        Returns:
            List of tuples containing (start_line, end_line) for each string literal.
        """
        ranges = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Str, ast.JoinedStr)):
                ranges.append((node.lineno, node.end_lineno))
        return ranges

    def _get_js_comment_ranges(self, content: str) -> List[tuple]:
        """Get line ranges for JavaScript/TypeScript comments.

        Args:
            content: The full content of the JavaScript/TypeScript file.

        Returns:
            List of tuples containing (start_line, end_line) for each comment.
        """
        ranges = []
        for pattern in self._comment_patterns["javascript"]:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                start_line = content[: match.start()].count("\n") + 1
                end_line = content[: match.end()].count("\n") + 1
                ranges.append((start_line, end_line))
        return ranges

    def _get_js_string_ranges(self, content: str) -> List[tuple]:
        """Get line ranges for JavaScript/TypeScript string literals.

        Args:
            content: The full content of the JavaScript/TypeScript file.

        Returns:
            List of tuples containing (start_line, end_line) for each string literal.
        """
        ranges = []
        for pattern in self._string_patterns["javascript"]:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                start_line = content[: match.start()].count("\n") + 1
                end_line = content[: match.end()].count("\n") + 1
                ranges.append((start_line, end_line))
        return ranges

    def _is_in_range(self, line_num: int, ranges: List[tuple]) -> bool:
        """Check if a line number falls within any of the given ranges.

        Args:
            line_num: The line number to check.
            ranges: List of tuples containing (start_line, end_line) ranges.

        Returns:
            True if line_num falls within any of the ranges, False otherwise.
        """
        return any(start <= line_num <= end for start, end in ranges)

    def _create_match_info(
        self,
        file_path: Path,
        line_num: int,
        line_text: str,
        all_lines: List[str],
        context_lines: int,
        include_line_numbers: bool,
    ) -> Dict[str, Any]:
        """Create a match info dictionary with context.

        Args:
            file_path: Path to the file containing the match.
            line_num: Zero-based line number of the match.
            line_text: Text content of the matching line.
            all_lines: List of all lines in the file.
            context_lines: Number of context lines to include before and after.
            include_line_numbers: Whether to include line numbers in output.

        Returns:
            Dictionary containing file, line_num (1-based), text, and context.
        """
        match_info: Dict[str, Any] = {
            "file": str(file_path),
            "line_num": line_num + 1,
            "text": line_text,
            "context": [],
        }

        if context_lines > 0:
            start_line = max(0, line_num - context_lines)
            end_line = min(len(all_lines), line_num + context_lines + 1)

            for ctx_i in range(start_line, end_line):
                if ctx_i != line_num:
                    context = match_info.get("context", [])
                    if isinstance(context, list):
                        context.append(
                            {
                                "line_num": ctx_i + 1,
                                "text": all_lines[ctx_i].rstrip("\n\r"),
                            }
                        )

        return match_info

    async def _enhanced_search(self, **kwargs: Any) -> ToolResult:
        """Enhanced search with language-specific features.

        Performs language-aware searching with support for excluding comments
        and string literals, language-specific file filtering, and enhanced
        pattern matching.

        Args:
            **kwargs: Keyword arguments including pattern, path, language,
                     exclude_comments, exclude_strings, etc.

        Returns:
            ToolResult containing search results with language-specific enhancements.
        """
        try:
            pattern = kwargs.get("pattern")
            if not pattern:
                return ToolResult(
                    success=False, output="", error="Pattern parameter is required"
                )
            path = kwargs.get("path", ".")
            file_pattern = kwargs.get("file_pattern", "*")
            recursive = kwargs.get("recursive", True)
            case_sensitive = kwargs.get("case_sensitive", True)
            whole_word = kwargs.get("whole_word", False)
            invert_match = kwargs.get("invert_match", False)
            context_lines = kwargs.get("context_lines", 0)
            max_matches = kwargs.get("max_matches", 100)
            include_line_numbers = kwargs.get("include_line_numbers", True)
            language = kwargs.get("language")
            exclude_comments = kwargs.get("exclude_comments", False)
            exclude_strings = kwargs.get("exclude_strings", False)

            search_path = Path(path).resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Search path does not exist: {path}",
                )

            # Compile regex pattern
            regex_flags = 0 if case_sensitive else re.IGNORECASE

            if whole_word:
                pattern = rf"\b{str(pattern)}\b"

            try:
                compiled_pattern: Pattern[str] = re.compile(str(pattern), regex_flags)
            except re.error as e:
                return ToolResult(
                    success=False, output="", error=f"Invalid regex pattern: {str(e)}"
                )

            # Find files to search
            files_to_search = []

            if search_path.is_file():
                files_to_search = [search_path]
            else:
                files_to_search = self._find_files(search_path, file_pattern, recursive)

            # Apply language filter if specified
            if language:
                lang_extensions = {
                    "python": [".py"],
                    "javascript": [".js", ".jsx", ".mjs"],
                    "typescript": [".ts", ".tsx"],
                    "java": [".java"],
                    "go": [".go"],
                    "rust": [".rs"],
                    "c": [".c", ".h"],
                    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
                    "csharp": [".cs"],
                    "ruby": [".rb"],
                    "php": [".php"],
                    "swift": [".swift"],
                    "kotlin": [".kt", ".kts"],
                    "scala": [".scala"],
                    "r": [".r", ".R"],
                    "julia": [".jl"],
                    "perl": [".pl", ".pm"],
                    "lua": [".lua"],
                    "bash": [".sh", ".bash"],
                    "powershell": [".ps1"],
                    "sql": [".sql"],
                    "html": [".html", ".htm"],
                    "css": [".css", ".scss", ".sass", ".less"],
                    "xml": [".xml"],
                    "yaml": [".yaml", ".yml"],
                    "json": [".json"],
                    "markdown": [".md", ".markdown"],
                }

                if language in lang_extensions:
                    extensions = lang_extensions[language]
                    files_to_search = [
                        f
                        for f in files_to_search
                        if any(f.suffix.lower() == ext for ext in extensions)
                    ]

            # Search in files
            all_matches: List[Dict[str, Any]] = []
            files_searched = 0

            for file_path in files_to_search:
                try:
                    matches = await self._search_file(
                        file_path,
                        compiled_pattern,
                        invert_match,
                        context_lines,
                        include_line_numbers,
                        exclude_comments,
                        exclude_strings,
                    )

                    if matches:
                        all_matches.extend(matches)

                    files_searched += 1

                    # Stop if we hit max matches
                    if len(all_matches) >= max_matches:
                        all_matches = all_matches[:max_matches]
                        break

                except Exception:  # nosec
                    # Skip files that can't be read
                    continue

            # Format output
            if not all_matches:
                output = f"No matches found for pattern: {pattern}"
                if language:
                    output += f" (language: {language})"
            else:
                output_lines = [
                    f"Found {len(all_matches)} matches in {files_searched} files:",
                    "",
                ]

                if language:
                    output_lines[0] += f" (language: {language})"

                current_file = None
                for match in all_matches:
                    if match["file"] != current_file:
                        current_file = match["file"]
                        relative_path = Path(current_file).relative_to(
                            search_path.parent if search_path.is_file() else search_path
                        )
                        output_lines.append(f"📄 {relative_path}:")

                    if include_line_numbers:
                        output_lines.append(
                            f"  {match['line_num']:4d}: {match['text']}"
                        )
                    else:
                        output_lines.append(f"  {match['text']}")

                    # Add context lines if any
                    for context in match.get("context", []):
                        if include_line_numbers:
                            output_lines.append(
                                f"  {context['line_num']:4d}| {context['text']}"
                            )
                        else:
                            output_lines.append(f"      | {context['text']}")

                if len(all_matches) >= max_matches:
                    output_lines.append(f"\n... truncated at {max_matches} matches")

                output = "\n".join(output_lines)

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pattern": pattern,
                    "matches_found": len(all_matches),
                    "files_searched": files_searched,
                    "search_path": str(search_path),
                    "language": language,
                    "exclude_comments": exclude_comments,
                    "exclude_strings": exclude_strings,
                    "matches": all_matches[:50],  # Limit metadata size
                },
            )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Enhanced search failed: {str(e)}"
            )
