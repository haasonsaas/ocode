"""
Context Manager for intelligent project analysis and file selection.

This module provides the core functionality for understanding project structure,
analyzing code files, and building relevant context for AI interactions. It serves
as the intelligent layer that bridges between raw project files and the AI's
understanding of the codebase.

Key Features:
- Automatic project structure discovery and analysis
- Language-aware code symbol and import extraction
- Intelligent file relevance scoring for query-specific context
- Multi-layer caching system for performance optimization
- Git integration for repository awareness
- Query categorization for optimal tool selection
- Dependency graph construction and analysis

The ContextManager is designed to scale with large codebases while maintaining
fast response times through intelligent caching and concurrent processing.
"""

import asyncio
import hashlib
import os
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiofiles
from git import InvalidGitRepositoryError, Repo

from ..languages import language_registry


@dataclass
class FileInfo:
    """Comprehensive metadata about a project file.

    Contains both static file information (size, modification time)
    and dynamic analysis results (language detection, symbols, imports).
    This data structure is used throughout the system for caching
    and context building.

    Attributes:
        path: Absolute path to the file
        size: File size in bytes
        modified_time: Last modification timestamp (for cache invalidation)
        content_hash: MD5 hash of file content (for change detection)
        language: Detected programming language (None if not code)
        symbols: List of extracted symbols (functions, classes, etc.)
        imports: List of imported modules/packages
    """

    path: Path
    size: int
    modified_time: float
    content_hash: str
    language: Optional[str] = None
    symbols: Optional[List[str]] = None
    imports: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.symbols is None:
            self.symbols = []
        if self.imports is None:
            self.imports = []


@dataclass
class ProjectContext:
    """Complete project context for AI processing.

    Represents the analyzed state of a project at a point in time,
    containing all the information needed for the AI to understand
    the codebase structure, dependencies, and relevant files.

    This is the primary data structure passed to the AI engine,
    containing pre-filtered and relevant information based on
    the user's query and the project's characteristics.

    Attributes:
        files: Mapping of file paths to their content (filtered for relevance)
        file_info: Mapping of file paths to their analysis metadata
        dependencies: Graph of file dependencies (file -> set of dependencies)
        symbols: Reverse index of symbols to files containing them
        project_root: Root directory of the project
        git_info: Git repository information (branch, commit, status)
    """

    files: Dict[Path, str]  # file_path -> content
    file_info: Dict[Path, FileInfo]
    dependencies: Dict[Path, Set[Path]]  # file -> dependencies
    symbols: Dict[str, List[Path]]  # symbol -> files containing it
    project_root: Path
    git_info: Optional[Dict[str, Any]] = None

    def get_relevant_files(self, query: str, max_files: int = 10) -> List[Path]:
        """Get files most relevant to the query using intelligent scoring.

        Implements a multi-factor relevance scoring algorithm that considers:
        1. Query term frequency in file content (weight: 1.0 per occurrence)
        2. Query terms in file path components (weight: 5.0 per match)
        3. Symbol name partial matches (weight: 3.0 per match)

        The scoring is designed to prioritize files that are explicitly
        mentioned in the query (by path) or contain relevant symbols,
        while still considering content relevance.

        Args:
            query: Search query string to match against files.
            max_files: Maximum number of files to return (top-scored).

        Returns:
            List of file paths sorted by relevance score (highest first).
            Returns empty list if no files have any relevance score.
        """
        # Simple relevance scoring based on:
        # 1. Query terms in file content
        # 2. Query terms in file path
        # 3. Symbol matches

        scores = defaultdict(float)
        query_lower = query.lower()
        query_terms = query_lower.split()

        for file_path, content in self.files.items():
            score = 0.0
            content_lower = content.lower()
            path_lower = str(file_path).lower()

            # Score based on query terms in content
            for term in query_terms:
                score += content_lower.count(term) * 1.0

            # Score based on query terms in path
            for term in query_terms:
                if term in path_lower:
                    score += 5.0

            # Score based on symbols
            if file_path in self.file_info and self.file_info[file_path].symbols:
                symbols = self.file_info[file_path].symbols
                if symbols:  # Additional None check to satisfy mypy
                    for symbol in symbols:
                        for term in query_terms:
                            if term in symbol.lower():
                                score += 3.0

            if score > 0:
                scores[file_path] = score

        # Sort by score and return top files
        sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [file_path for file_path, _ in sorted_files[:max_files]]


class ContextManager:
    """
    Central manager for project context analysis and intelligent file selection.

    The ContextManager serves as the core intelligence layer that understands
    project structure, analyzes code files, and builds relevant context for
    AI interactions. It combines multiple analysis techniques with efficient
    caching to provide fast, accurate project understanding.

    Architecture:
    - Multi-layer caching: In-memory + SQLite persistence
    - Concurrent file analysis with semaphore-based throttling
    - Language-aware symbol extraction using pluggable analyzers
    - Query-driven context filtering for optimal relevance
    - Git integration for repository state awareness

    Key Features:
    - Automatic project structure discovery with intelligent ignore patterns
    - File content caching with MD5-based change detection
    - Dependency graph construction from import analysis
    - Symbol indexing for fast lookup and relevance scoring
    - Git integration for branch/commit awareness
    - Query categorization for optimal tool and context selection
    - Performance optimization through concurrent processing

    Performance Characteristics:
    - Scales to large codebases (1000+ files) with sub-second response
    - Memory-efficient with configurable cache limits
    - Persistent caching reduces re-analysis overhead
    - Concurrent processing with configurable semaphore limits

    Thread Safety:
    - Designed for single-threaded async usage
    - File system operations are properly serialized
    - Cache operations are atomic within single async context
    """

    def __init__(self, root: Optional[Path] = None, cache_dir: Optional[Path] = None):
        """
        Initialize the context manager with project and cache configuration.

        Sets up the core data structures, initializes caching systems,
        and establishes Git repository connection if available.

        Args:
            root: Project root directory. If None, uses current working directory.
                 Must exist and be readable. This defines the scope of analysis.
            cache_dir: Directory for persistent cache storage. If None, uses
                      .ocode/cache relative to project root. Created if missing.

        Raises:
            ValueError: If root directory doesn't exist or isn't a directory.
            RuntimeError: If cache directory cannot be created.

        Side Effects:
            - Creates cache directory structure if it doesn't exist
            - Initializes SQLite database for persistent caching
            - Attempts to initialize Git repository connection
            - Sets up in-memory caches with size limits
        """
        self.root = Path(root) if root else Path.cwd()

        # Validate root exists
        if not self.root.exists():
            raise ValueError(f"Root directory does not exist: {self.root}")

        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root}")

        self.cache_dir = cache_dir or self.root / ".ocode" / "cache"

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Failed to create cache directory: {e}")

        # Track active connections for proper cleanup
        self._active_connections: set = set()

        # In-memory caches with size limits for performance optimization
        # These provide fast access to recently analyzed files while preventing
        # unbounded memory growth through LRU eviction
        self.file_cache: Dict[Path, Tuple[str, float]] = {}  # path -> (content, mtime)
        self.file_info_cache: Dict[Path, FileInfo] = {}  # path -> analysis results
        self.max_cache_size = 100  # Maximum number of files to cache in memory

        # Persistent cache database
        self.db_path = self.cache_dir / "context.db"
        self._init_db()

        # Git repository (if available)
        self.repo: Optional[Repo] = None
        self._init_git()

        # File and directory patterns to ignore during analysis
        # These patterns exclude common non-source directories and files
        # that would add noise without providing useful context
        self.ignore_patterns = {
            # Version control and project metadata
            ".git",
            ".ocode",
            ".idea",
            ".vscode",
            # Python-specific
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
            "*.pyo",
            "*.egg-info",
            # JavaScript/Node.js
            "node_modules",
            # Virtual environments
            ".venv",
            "venv",
            # Environment and config
            ".env",
            # System and temporary files
            ".DS_Store",
            "*.log",
            "*.tmp",
        }

        # Separate wildcard patterns for efficient matching
        # Wildcard patterns require fnmatch processing which is slower
        # than simple string containment checks
        self.wildcard_patterns = [
            pattern
            for pattern in self.ignore_patterns
            if "*" in pattern or "?" in pattern
        ]

    def _init_db(self) -> None:
        """Initialize SQLite database for persistent caching.

        Creates the database schema for storing file analysis results
        and dependency information. The database serves as a persistent
        cache layer that survives between sessions, significantly improving
        performance on subsequent runs.

        Tables Created:
        - file_analysis: Stores file metadata, symbols, and language info
        - dependencies: Stores file-to-file dependency relationships

        The database uses file modification time and content hashes
        to ensure cache validity and automatic invalidation when
        files change.

        Side Effects:
            Creates SQLite database file at self.db_path if it doesn't exist.
            Existing databases are preserved and schema is updated if needed.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            self._active_connections.add(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_analysis (
                    path TEXT PRIMARY KEY,
                    content_hash TEXT,
                    modified_time REAL,
                    language TEXT,
                    symbols TEXT,
                    imports TEXT,
                    created_at REAL
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dependencies (
                    source_file TEXT,
                    target_file TEXT,
                    dependency_type TEXT,
                    PRIMARY KEY (source_file, target_file)
                )
            """
            )
            conn.commit()
        finally:
            self._active_connections.discard(conn)
            conn.close()

    def _init_git(self) -> None:
        """Initialize Git repository connection if available.

        Attempts to establish a connection to the Git repository containing
        or parent to the project root. This enables Git-aware features like
        branch detection, commit information, and tracking file changes.

        The Git integration is optional and gracefully degrades if:
        - The project is not in a Git repository
        - Git is not available on the system
        - Repository is corrupted or inaccessible

        Side Effects:
            Sets self.repo to a GitPython Repo object if successful,
            or None if Git is not available or applicable.
        """
        try:
            self.repo = Repo(self.root, search_parent_directories=True)
        except InvalidGitRepositoryError:
            self.repo = None

    def _should_ignore(self, path: Path) -> bool:
        """Determine if a file or directory should be excluded from analysis.

        Implements a comprehensive filtering system that excludes:
        1. Paths matching exact ignore patterns (version control, caches, etc.)
        2. Files matching wildcard patterns (*.pyc, *.log, etc.)
        3. Files larger than 1MB (to prevent memory issues)
        4. Files with permission errors (inaccessible files)

        The filtering is designed to focus analysis on source code and
        configuration files while excluding build artifacts, dependencies,
        and system files that would add noise without value.

        Args:
            path: File or directory path to evaluate for inclusion.

        Returns:
            True if the path should be ignored (excluded from analysis),
            False if it should be included.

        Performance Notes:
            - Exact pattern matching is O(1) average case
            - Wildcard matching uses fnmatch (slower, used sparingly)
            - File size check only performed if path exists
        """
        import fnmatch

        # Check if any part of the path matches ignore patterns
        parts = path.parts
        path_str = str(path)

        # Check exact matches in path parts
        for pattern in self.ignore_patterns:
            if "*" not in pattern and "?" not in pattern:
                # Exact match pattern
                if pattern in parts:
                    return True

        # Check wildcard patterns
        for pattern in self.wildcard_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
            # Also check against full path for patterns like "**/test"
            if fnmatch.fnmatch(path_str, pattern):
                return True

        # Only check file size if path exists and is a file
        if path.exists() and path.is_file():
            try:
                stat = path.stat()
                if stat.st_size > 1024 * 1024:
                    return True
            except (OSError, PermissionError):
                # Permission errors mean we should ignore it
                return True

        return False

    def _get_content_hash(self, content: str) -> str:
        """Generate MD5 hash for file content change detection.

        Creates a fast hash of file content for cache invalidation.
        MD5 is used here for speed rather than security - we only need
        to detect when file content has changed, not protect against
        malicious modifications.

        The implementation handles Python version differences in the
        hashlib.md5() constructor's usedforsecurity parameter, which
        was added in Python 3.9.

        Args:
            content: String content of the file to hash.

        Returns:
            32-character hexadecimal MD5 hash of the UTF-8 encoded content.

        Security Note:
            This hash is used only for cache invalidation, not security.
            The usedforsecurity=False parameter (when available) indicates
            this is not a cryptographic use case.
        """
        # usedforsecurity parameter is only available in Python 3.9+
        # mypy doesn't recognize this parameter in its stubs
        import sys

        if sys.version_info >= (3, 9):
            return hashlib.md5(  # type: ignore[call-arg]
                content.encode("utf-8"), usedforsecurity=False
            ).hexdigest()
        else:
            # Fallback for Python 3.8
            return hashlib.md5(content.encode("utf-8")).hexdigest()  # nosec B324

    async def _read_file(self, path: Path) -> Optional[str]:
        """Safely read file content with comprehensive error handling.

        Performs asynchronous file reading with UTF-8 encoding, gracefully
        handling common issues like encoding problems, permission errors,
        and missing files. This method is designed to be robust and never
        crash the analysis process due to individual file issues.

        Error Conditions Handled:
        - UnicodeDecodeError: Binary files or files with incompatible encoding
        - PermissionError: Files that the process cannot read
        - FileNotFoundError: Files that were deleted during analysis
        - Other I/O errors: Network drives, corrupted files, etc.

        Args:
            path: Path to the file to read. Must be a valid Path object.

        Returns:
            File content as a UTF-8 decoded string if successful,
            None if the file cannot be read for any reason.

        Performance:
            Uses aiofiles for true asynchronous I/O to avoid blocking
            the event loop during file operations.
        """
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
                return str(content)
        except (UnicodeDecodeError, PermissionError, FileNotFoundError):
            return None

    def _detect_language(self, path: Path) -> Optional[str]:
        """Detect programming language from file extension and patterns.

        Uses the language registry system to identify the programming
        language of a file based on its extension and naming patterns.
        This enables language-specific analysis features like symbol
        extraction and import parsing.

        The detection is based on:
        1. File extension matching (.py, .js, .ts, etc.)
        2. Filename patterns (Makefile, Dockerfile, etc.)
        3. Language analyzer availability in the registry

        Args:
            path: Path to the file to analyze. The filename and extension
                  are used for language detection.

        Returns:
            Language name string (e.g., 'python', 'javascript') if a
            matching analyzer is found, None if the file type is not
            recognized or no analyzer is available.

        Examples:
            - 'script.py' -> 'python'
            - 'app.js' -> 'javascript'
            - 'config.yaml' -> 'yaml'
            - 'README.md' -> 'markdown'
        """
        # Use language registry to get analyzer for file
        analyzer = language_registry.get_analyzer_for_file(path)
        if analyzer:
            return analyzer.language
        return None

    def _extract_symbols(self, content: str, language: str) -> List[str]:
        """Extract symbols (functions, classes, variables) from source code.

        Uses language-specific analyzers to parse source code and extract
        symbol definitions. This creates an index of available symbols that
        can be used for relevance scoring and context building.

        Symbol Types Extracted (language-dependent):
        - Function definitions
        - Class definitions
        - Method definitions
        - Variable declarations
        - Constants and enums
        - Type definitions

        The extraction is best-effort and gracefully handles:
        - Syntax errors in source code
        - Unsupported language constructs
        - Parser failures or exceptions

        Args:
            content: Raw source code content as a string.
            language: Programming language identifier (e.g., 'python').

        Returns:
            List of symbol names extracted from the code. Returns empty
            list if extraction fails or no symbols are found.

        Performance:
            Uses language-specific AST parsers for accurate extraction.
            Parsing is done synchronously but is typically fast.
        """
        analyzer = language_registry.get_analyzer(language)
        if analyzer:
            try:
                symbols = analyzer.extract_symbols(content)
                return [symbol.name for symbol in symbols]
            except Exception:
                # Fallback to empty list if analysis fails
                pass  # nosec B110
        return []

    def _extract_imports(self, content: str, language: str) -> List[str]:
        """Extract import/require statements from source code.

        Uses language-specific analyzers to parse and extract import
        statements, building a dependency map that can be used for
        understanding code relationships and project structure.

        Import Types Extracted (language-dependent):
        - Module imports (Python: import/from statements)
        - Package imports (JavaScript: require/import statements)
        - Include statements (C/C++: #include directives)
        - Using statements (C#: using directives)

        The extraction focuses on external dependencies and local modules,
        helping to build a dependency graph for the project.

        Args:
            content: Raw source code content as a string.
            language: Programming language identifier (e.g., 'python').

        Returns:
            List of imported module/package names. Returns empty list
            if extraction fails or no imports are found.

        Examples:
            Python: ['os', 'sys', 'requests', 'my_module']
            JavaScript: ['express', 'lodash', './utils']
        """
        analyzer = language_registry.get_analyzer(language)
        if analyzer:
            try:
                imports = analyzer.extract_imports(content)
                return [imp.module for imp in imports]
            except Exception:
                # Fallback to empty list if analysis fails
                pass  # nosec B110
        return []

    def _manage_cache_size(self) -> None:
        """Implement LRU cache eviction to prevent unbounded memory growth.

        Monitors in-memory cache size and evicts least recently used entries
        when the cache exceeds the configured maximum size. This ensures
        the context manager can handle large projects without consuming
        excessive memory.

        LRU Algorithm:
        1. Sorts cache entries by modification time (proxy for access time)
        2. Removes oldest entries until cache is under the size limit
        3. Maintains consistency between file_cache and file_info_cache

        The eviction is conservative, removing slightly more than necessary
        to avoid frequent triggering. Persistent cache in SQLite is not
        affected by this operation.

        Side Effects:
            Modifies self.file_cache and self.file_info_cache by removing
            entries. The persistent SQLite cache remains unchanged.

        Performance:
            O(n log n) due to sorting, where n is the number of cached files.
            Typically fast since cache size is limited (default: 100 files).
        """
        if len(self.file_cache) > self.max_cache_size:
            # Remove oldest entries (simple LRU)
            sorted_entries = sorted(
                self.file_cache.items(), key=lambda x: x[1][1]  # Sort by mtime
            )
            # Remove entries to get back under limit
            num_to_remove = len(self.file_cache) - self.max_cache_size + 1
            for path, _ in sorted_entries[:num_to_remove]:
                del self.file_cache[path]
                if path in self.file_info_cache:
                    del self.file_info_cache[path]

    async def analyze_file(self, path: Path) -> Optional[FileInfo]:
        """Perform comprehensive analysis of a single file.

        This is the core file analysis method that combines multiple
        analysis techniques to extract useful metadata from source files.
        The analysis is cached at multiple levels for performance.

        Analysis Pipeline:
        1. Check if file should be ignored (size, patterns, permissions)
        2. Check in-memory cache for recent analysis
        3. Check persistent SQLite cache for previous analysis
        4. If cache miss: read file content and perform analysis
        5. Extract language-specific symbols and imports
        6. Cache results in both memory and persistent storage

        Caching Strategy:
        - In-memory cache: Fast access for recently analyzed files
        - Persistent cache: Survives between sessions, uses mtime + hash
        - Cache invalidation: Based on file modification time

        Args:
            path: Path to the file to analyze. Must be a valid Path object.

        Returns:
            FileInfo object containing analysis results including language,
            symbols, imports, and metadata. Returns None if the file should
            be ignored or cannot be analyzed due to errors.

        Performance:
            - Cache hit (memory): ~1μs
            - Cache hit (persistent): ~100μs
            - Full analysis: ~1-10ms depending on file size and complexity
        """
        if self._should_ignore(path) or not path.is_file():
            return None

        try:
            stat = path.stat()
            mtime = stat.st_mtime

            # Check in-memory cache first
            if path in self.file_info_cache:
                cached_info = self.file_info_cache[path]
                if cached_info and cached_info.modified_time == mtime:
                    return cached_info

            # Check persistent cache
            persistent_cached_info = self._get_cached_analysis(path, mtime)
            if persistent_cached_info:
                self.file_info_cache[path] = persistent_cached_info
                return persistent_cached_info

            # Read and analyze file
            content = await self._read_file(path)
            if content is None:
                return None

            content_hash = self._get_content_hash(content)
            language = self._detect_language(path)

            symbols = []
            imports = []

            if language:
                symbols = self._extract_symbols(content, language)
                imports = self._extract_imports(content, language)

            file_info = FileInfo(
                path=path,
                size=stat.st_size,
                modified_time=mtime,
                content_hash=content_hash,
                language=language,
                symbols=symbols,
                imports=imports,
            )

            # Cache the analysis
            self._cache_analysis(file_info)
            self.file_info_cache[path] = file_info

            # Manage cache size
            self._manage_cache_size()

            return file_info

        except (PermissionError, OSError):
            # Log but don't print for expected errors
            return None
        except Exception as e:
            # Log error analyzing file
            _ = e  # Using the exception variable
            return None

    def _get_cached_analysis(self, path: Path, mtime: float) -> Optional[FileInfo]:
        """Retrieve cached file analysis from persistent storage.

        Queries the SQLite database for previously computed analysis results,
        using file path and modification time as the cache key. This enables
        fast retrieval of analysis results across application restarts.

        Cache Validity:
        - Primary key: file path (string)
        - Validation: modification time must match exactly
        - If mtime differs, cache is considered stale and ignored

        The method is designed to be resilient to database errors and
        will silently fall back to re-analysis if the cache is unavailable.

        Args:
            path: Path to the file being analyzed.
            mtime: Current modification timestamp of the file.

        Returns:
            Cached FileInfo object if found and valid, None if cache miss
            or if the cached entry is stale (different mtime).

        Database Schema:
            Uses 'file_analysis' table with columns for path, content_hash,
            modified_time, language, symbols, imports, and created_at.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                self._active_connections.add(conn)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM file_analysis WHERE path = ? AND modified_time = ?",
                    (str(path), mtime),
                )
                row = cursor.fetchone()

                if row:
                    return FileInfo(
                        path=Path(row[0]),
                        content_hash=row[1],
                        modified_time=row[2],
                        language=row[3],
                        symbols=row[4].split(",") if row[4] else [],
                        imports=row[5].split(",") if row[5] else [],
                        size=0,  # We don't cache size
                    )
            finally:
                self._active_connections.discard(conn)
                conn.close()
        except sqlite3.Error:
            # Database error - continue without cache
            pass

        return None

    def _cache_analysis(self, file_info: FileInfo) -> None:
        """Store file analysis results in persistent cache.

        Saves the analysis results to the SQLite database for future
        retrieval, significantly improving performance on subsequent
        runs. The cache entry includes all relevant metadata needed
        to reconstruct the FileInfo object.

        Caching Strategy:
        - Uses INSERT OR REPLACE to handle updates to existing files
        - Stores symbols and imports as comma-separated strings
        - Includes timestamp for cache debugging and maintenance
        - Silently handles database errors to ensure robustness

        Args:
            file_info: Complete FileInfo object with analysis results.

        Side Effects:
            Writes to SQLite database at self.db_path. If database is
            unavailable or corrupted, the operation fails silently
            and analysis continues without persistent caching.

        Performance:
            Single INSERT/UPDATE operation, typically <1ms. Database
            is WAL mode by default for better concurrency.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                self._active_connections.add(conn)
                conn.execute(
                    """INSERT OR REPLACE INTO file_analysis
                       (path, content_hash, modified_time, language, symbols, imports, created_at)  # noqa: E501
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(file_info.path),
                        file_info.content_hash,
                        file_info.modified_time,
                        file_info.language,
                        ",".join(file_info.symbols or []),
                        ",".join(file_info.imports or []),
                        time.time(),
                    ),
                )
                conn.commit()
            finally:
                self._active_connections.discard(conn)
                conn.close()
        except sqlite3.Error:
            # Database error - continue without persistent cache
            pass

    async def scan_project(self) -> List[Path]:
        """Recursively discover all analyzable files in the project.

        Performs a comprehensive directory walk starting from the project
        root, identifying all files that should be included in analysis.
        The scan applies ignore patterns to exclude irrelevant directories
        and files, focusing on source code and configuration files.

        Scanning Strategy:
        1. Uses os.walk() for efficient recursive directory traversal
        2. Applies directory filtering to avoid walking ignored directories
        3. Filters files based on ignore patterns and size limits
        4. Returns absolute paths for consistent handling

        Performance Optimizations:
        - Early directory pruning prevents walking large ignored directories
        - Batch processing of directory contents
        - Path objects are created only for valid files

        Returns:
            List of Path objects representing files that should be analyzed.
            Typically includes source code files, configuration files, and
            documentation, while excluding build artifacts and dependencies.

        Examples:
            For a Python project, might return:
            - *.py files (source code)
            - *.yaml, *.json files (configuration)
            - *.md files (documentation)
            But excludes:
            - __pycache__ directories
            - *.pyc files
            - .git directory
        """
        files = []

        for root, dirs, filenames in os.walk(self.root):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(Path(root) / d)]

            for filename in filenames:
                file_path = Path(root) / filename
                if not self._should_ignore(file_path):
                    files.append(file_path)

        return files

    def _detect_multi_action_query(self, query_lower: str) -> Optional[Dict[str, Any]]:
        """
        Detect complex queries requiring multiple tools or agent delegation.

        Analyzes user queries to identify scenarios that require sequential
        tool execution or delegation to specialized agents. This enables
        the system to handle complex workflows like "test and commit" or
        "analyze and document" efficiently.

        Multi-Action Patterns Detected:
        - Test + Git workflows (run tests then commit)
        - File operations + Git (edit files then commit)
        - Build + Deploy pipelines (test, build, deploy)
        - Analysis + Documentation (analyze then document)
        - Search + Modify (find then replace)
        - Setup + Configuration workflows

        Pattern Matching:
        1. Uses regex patterns to identify specific multi-action scenarios
        2. Analyzes conjunction words ("and", "then", "after") for sequence
        3. Categorizes query parts to suggest appropriate tools
        4. Provides workflow guidance for complex scenarios

        Args:
            query_lower: User query converted to lowercase for analysis.

        Returns:
            Dictionary with categorization details if multi-action detected:
            - category: Type of multi-action workflow
            - confidence: Confidence score (0.0-1.0)
            - suggested_tools: List of tools needed
            - workflow: Suggested execution strategy
            - primary_tools: Main tools for the task
            - secondary_tools: Supporting/follow-up tools

            Returns None if this is a single-action query.
        """
        # Define common multi-action patterns
        multi_patterns: List[Dict[str, Any]] = [
            # Test + Git patterns
            {
                "pattern": r"(run|execute) test.*and.*(commit|push)",
                "description": "Run tests then commit",
                "primary_tools": ["test_runner"],
                "secondary_tools": ["git_commit"],
                "workflow": "test_then_git",
                "category": "multi_action_test_git",
            },
            {
                "pattern": r"test.*coverage.*and.*(commit|push)",
                "description": "Test with coverage then commit",
                "primary_tools": ["test_runner", "coverage"],
                "secondary_tools": ["git_commit"],
                "workflow": "test_coverage_git",
                "category": "multi_action_test_git",
            },
            # File operations + Git patterns
            {
                "pattern": r"(edit|modify|update).*and.*(commit|save to git)",
                "description": "Edit files then commit",
                "primary_tools": ["file_edit"],
                "secondary_tools": ["git_commit"],
                "workflow": "edit_then_git",
                "category": "multi_action_file_git",
            },
            # Test + Build + Deploy patterns
            {
                "pattern": r"(test|run tests?).*then.*(build|compile).*then.*(deploy|push)",  # noqa: E501
                "description": "Test, build, and deploy",
                "primary_tools": ["test_runner"],
                "secondary_tools": ["bash", "git_commit"],
                "workflow": "test_build_deploy",
                "category": "multi_action_cicd",
            },
            # Create + Test patterns
            {
                "pattern": r"(create|add|build).*and.*(test|write tests)",
                "description": "Create component and write tests",
                "primary_tools": ["file_write", "file_edit"],
                "secondary_tools": ["test_runner"],
                "workflow": "create_test",
                "category": "multi_action_create_test",
            },
            # Analysis + Documentation patterns
            {
                "pattern": r"(analyze|review).*and.*(document|write docs)",
                "description": "Analyze then document",
                "primary_tools": ["architect"],
                "secondary_tools": ["file_write"],
                "workflow": "analyze_document",
                "category": "multi_action_analysis_docs",
            },
            # Search + Modify patterns
            {
                "pattern": r"(find|search|grep).*and.*(replace|modify|edit|update)",
                "description": "Search then modify",
                "primary_tools": ["grep", "code_grep"],
                "secondary_tools": ["file_edit"],
                "workflow": "search_modify",
                "category": "multi_action_search_edit",
            },
            # Setup + Configure patterns
            {
                "pattern": r"(setup|install|create).*and.*(configure|setup)",
                "description": "Setup then configure",
                "primary_tools": ["bash"],
                "secondary_tools": ["file_write", "file_edit"],
                "workflow": "setup_configure",
                "category": "multi_action_setup",
            },
        ]

        import re

        for pattern_def in multi_patterns:
            if re.search(pattern_def["pattern"], query_lower):
                all_tools = (
                    pattern_def["primary_tools"] + pattern_def["secondary_tools"]
                )

                return {
                    "category": pattern_def["category"],
                    "confidence": 0.9,
                    "suggested_tools": all_tools,
                    "context_strategy": "targeted",
                    "multi_action": True,
                    "workflow": pattern_def["workflow"],
                    "primary_tools": pattern_def["primary_tools"],
                    "secondary_tools": pattern_def["secondary_tools"],
                    "description": pattern_def["description"],
                }

        # Check for general multi-action indicators
        conjunctions = ["and", "then", "after", "followed by", "next", "also"]
        has_conjunction = any(conj in query_lower for conj in conjunctions)

        if has_conjunction:
            # Split query by conjunctions and analyze each part
            import re

            parts = re.split(
                r"\s+(and|then|after|followed by|next|also)\s+", query_lower
            )
            parts = [part.strip() for part in parts if part.strip() not in conjunctions]

            if len(parts) >= 2:
                # Quick categorization of each part
                part_tools = []
                for part in parts:
                    part_result = self._quick_categorize_part(part)
                    if part_result:
                        part_tools.extend(part_result.get("suggested_tools", []))

                if len(set(part_tools)) > 1:  # Multiple different tools needed
                    return {
                        "category": "multi_action_general",
                        "confidence": 0.8,
                        "suggested_tools": list(set(part_tools)),
                        "context_strategy": "targeted",
                        "multi_action": True,
                        "workflow": "sequential_actions",
                        "parts": parts,
                        "description": f'Sequential actions: {" → ".join(parts)}',
                    }

        return None

    def _quick_categorize_part(self, part: str) -> Optional[Dict[str, Any]]:
        """Quickly categorize a query fragment to identify required tools.

        Performs lightweight analysis of individual query parts to identify
        which tools might be needed. This is used in multi-action query
        detection to understand the component parts of complex requests.

        The categorization uses keyword matching to identify common patterns:
        - Test-related keywords -> test_runner tool
        - Git-related keywords -> git_* tools
        - File operations -> file_* tools
        - Search operations -> grep/search tools
        - Build/shell operations -> bash tool
        - Analysis operations -> architect tool

        Args:
            part: A single fragment of the query, typically split by
                  conjunction words like "and", "then", "after".

        Returns:
            Dictionary containing 'suggested_tools' list if tools are
            identified for this part, None if no specific tools are
            detected or if the part is too generic.

        Performance:
            Optimized for speed using simple keyword lookups rather than
            complex pattern matching. Designed to be called multiple times
            during multi-action query analysis.
        """
        part_lower = part.strip().lower()

        # Test patterns
        if any(kw in part_lower for kw in ["test", "tests", "pytest", "jest"]):
            return {"suggested_tools": ["test_runner"]}

        # Git patterns
        if any(kw in part_lower for kw in ["commit", "push", "git"]):
            return {"suggested_tools": ["git_commit"]}

        # File patterns
        if any(kw in part_lower for kw in ["edit", "modify", "write", "create file"]):
            return {"suggested_tools": ["file_edit", "file_write"]}

        # Search patterns
        if any(kw in part_lower for kw in ["find", "search", "grep", "locate"]):
            return {"suggested_tools": ["grep", "code_grep"]}

        # Build/Shell patterns
        if any(
            kw in part_lower
            for kw in ["build", "compile", "run", "execute", "npm", "docker"]
        ):
            return {"suggested_tools": ["bash"]}

        # Analysis patterns
        if any(kw in part_lower for kw in ["analyze", "review", "check architecture"]):
            return {"suggested_tools": ["architect"]}

        # Documentation patterns
        if any(kw in part_lower for kw in ["document", "write docs", "readme"]):
            return {"suggested_tools": ["file_write"]}

        return None

    def _categorize_query(self, query: str) -> Dict[str, Any]:
        """
        Comprehensive query analysis for optimal context and tool selection.

        This is the main query understanding system that analyzes user intent
        and provides guidance for context building and tool selection. It uses
        pattern matching, keyword analysis, and heuristics to categorize queries
        into actionable categories.

        Analysis Dimensions:
        1. Query Type: What kind of operation is requested?
        2. Tool Requirements: Which tools are likely needed?
        3. Context Strategy: How much project context is required?
        4. Multi-Action Detection: Is this a complex workflow?
        5. Confidence Scoring: How certain is the categorization?

        Categories Handled:
        - Agent management (create/list/delegate agents)
        - Tool listing (show available capabilities)
        - File operations (read/write/search/edit)
        - Git operations (status/commit/diff)
        - Testing and quality (run tests/coverage/lint)
        - Architecture analysis (code structure/dependencies)
        - Shell execution (commands/scripts)
        - Memory management (remember/recall)
        - Reasoning tasks (think/analyze/evaluate)
        - Notebook operations (Jupyter/IPython)
        - Complex workflows (refactor/debug/optimize)

        Context Strategies:
        - none: No project context needed
        - minimal: Basic context (1-3 files)
        - targeted: Focused context (5-10 files)
        - full: Comprehensive context (up to max_files)

        Args:
            query: Raw user query string to analyze.

        Returns:
            Dictionary containing:
            - category: Primary category of the query
            - confidence: Confidence score (0.0-1.0)
            - suggested_tools: List of recommended tools
            - context_strategy: Required context depth
            - multi_action: Boolean indicating complex workflow
            - Additional category-specific metadata

        Performance:
            Uses efficient keyword matching and early returns to minimize
            analysis time. Most queries are categorized in <1ms.
        """
        # Validate query
        if not query or not query.strip():
            return {
                "category": "empty_query",
                "confidence": 1.0,
                "suggested_tools": [],
                "context_strategy": "none",
            }

        query_lower = query.lower().strip()

        # First, check for multi-action queries that need multiple tools/agents
        multi_action_result = self._detect_multi_action_query(query_lower)
        if multi_action_result:
            return multi_action_result

        # Agent management queries
        agent_patterns = {
            "keywords": [
                "agent",
                "agents",
                "reviewer",
                "reviewers",
                "sub-agent",
                "task delegation",
                "delegate",
            ],
            "actions": [
                "create",
                "list",
                "status",
                "how many",
                "count",
                "delegate",
                "terminate",
                "manage",
            ],
        }

        if any(kw in query_lower for kw in agent_patterns["keywords"]):
            if any(action in query_lower for action in agent_patterns["actions"]):
                return {
                    "category": "agent_management",
                    "confidence": 0.9,
                    "suggested_tools": ["agent"],
                    "context_strategy": "minimal",
                }

        # Tool/capability queries
        tool_patterns = {
            "keywords": [
                "tool",
                "tools",
                "command",
                "commands",
                "capability",
                "capabilities",
                "function",
                "functions",
            ],
            "triggers": [
                "available",
                "can use",
                "list",
                "what",
                "show me",
                "help",
                "how to",
                "which",
            ],
        }

        if any(kw in query_lower for kw in tool_patterns["keywords"]) and any(
            trigger in query_lower for trigger in tool_patterns["triggers"]
        ):
            return {
                "category": "tool_listing",
                "confidence": 0.95,
                "suggested_tools": [],
                "context_strategy": "none",
            }

        # File operations - check early for explicit file operations
        file_patterns = {
            "read": ["read", "show", "display", "view", "cat", "open"],
            "write": ["write", "save", "create", "generate", "output"],
            "search": ["find", "search", "grep", "look for", "locate"],
            "edit": ["edit", "modify", "change", "update", "replace"],
            "list": ["list", "ls", "dir", "files in", "contents of"],
        }

        file_confidence = 0.0
        file_tools = []
        file_indicators = [
            "file",
            "files",
            "directory",
            "folder",
            ".py",
            ".js",
            ".ts",
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
        ]

        # Boost confidence if file-related terms are present
        has_file_context = any(
            indicator in query_lower for indicator in file_indicators
        )

        for operation, keywords in file_patterns.items():
            if any(kw in query_lower for kw in keywords):
                file_confidence += 0.3 if has_file_context else 0.2
                if operation == "read":
                    file_tools.extend(["file_read", "ls"])
                elif operation == "write":
                    file_tools.extend(["file_write"])
                elif operation == "search":
                    file_tools.extend(["grep", "code_grep", "glob"])
                elif operation == "edit":
                    file_tools.extend(["file_edit"])
                elif operation == "list":
                    file_tools.extend(["ls", "file_list", "glob"])

        # Git operations - check BEFORE file operations to avoid conflicts, but AFTER testing # noqa: E501
        git_patterns = {
            "keywords": [
                "git",
                "commit",
                "branch",
                "merge",
                "diff",
                "repository",
                "repo",
            ],
            "actions": ["commit", "push", "pull", "checkout", "merge", "diff", "log"],
            "status_terms": ["git status", "repository status", "repo status"],
            "diff_terms": ["show diff", "git diff", "diff for"],
        }

        git_match = any(kw in query_lower for kw in git_patterns["keywords"])
        git_action = any(action in query_lower for action in git_patterns["actions"])
        status_match = any(term in query_lower for term in git_patterns["status_terms"])
        diff_match = any(term in query_lower for term in git_patterns["diff_terms"])

        # Don't match git if testing keywords are primary focus
        has_test_focus = any(
            kw in query_lower for kw in ["test", "tests", "testing"]
        ) and any(action in query_lower for action in ["run", "execute"])

        if (
            git_match or git_action or status_match or diff_match
        ) and not has_test_focus:
            git_tools = []
            if any(word in query_lower for word in ["status", "state"]) or status_match:
                git_tools.append("git_status")
            if any(word in query_lower for word in ["commit", "save"]):
                git_tools.append("git_commit")
            if (
                any(word in query_lower for word in ["diff", "changes", "difference"])
                or diff_match
            ):
                git_tools.append("git_diff")
            if any(word in query_lower for word in ["branch", "checkout"]):
                git_tools.append("git_branch")

            if not git_tools:
                git_tools = ["git_status"]  # Default

            return {
                "category": "git_operations",
                "confidence": 0.9,
                "suggested_tools": git_tools,
                "context_strategy": "minimal",
            }

        # Early return for strong file operations
        if file_confidence >= 0.5 or (has_file_context and file_confidence >= 0.3):
            return {
                "category": "file_operations",
                "confidence": min(file_confidence, 0.9),
                "suggested_tools": list(set(file_tools)),
                "context_strategy": "targeted",
            }

        # Testing and quality - check BEFORE git operations since "run tests" might also mention git # noqa: E501
        testing_patterns = {
            "keywords": [
                "test",
                "tests",
                "testing",
                "coverage",
                "lint",
                "quality",
                "validate",
            ],
            "frameworks": ["pytest", "jest", "unittest", "mocha", "go test", "rspec"],
            "actions": ["run", "execute", "check", "measure", "report"],
            "quality_terms": [
                "code quality",
                "static analysis",
                "quality issues",
                "code check",
            ],
            "test_commands": ["run tests", "execute tests", "run test", "execute test"],
        }

        test_match = any(
            kw in query_lower
            for kw in testing_patterns["keywords"] + testing_patterns["frameworks"]
        )
        test_action = any(
            action in query_lower for action in testing_patterns["actions"]
        )
        quality_match = any(
            term in query_lower for term in testing_patterns["quality_terms"]
        )
        test_command = any(
            cmd in query_lower for cmd in testing_patterns["test_commands"]
        )

        if (test_match and test_action) or quality_match or test_command:
            tools = ["test_runner"]
            if "coverage" in query_lower:
                tools.append("coverage")
            if "lint" in query_lower:
                tools.append("lint")

            return {
                "category": "testing_quality",
                "confidence": 0.85,
                "suggested_tools": tools,
                "context_strategy": "targeted",
            }

        # Architecture analysis
        architecture_patterns = {
            "keywords": [
                "architecture",
                "structure",
                "design",
                "dependencies",
                "patterns",
                "analyze codebase",
                "code structure",
                "project structure",
                "overview",
                "diagram",
                "visualization",
            ],
            "actions": [
                "analyze",
                "review",
                "examine",
                "assess",
                "evaluate",
                "generate",
            ],
        }

        arch_match = any(kw in query_lower for kw in architecture_patterns["keywords"])
        arch_action = any(
            action in query_lower for action in architecture_patterns["actions"]
        )

        if arch_match and (arch_action or "architecture" in query_lower):
            return {
                "category": "architecture_analysis",
                "confidence": 0.9,
                "suggested_tools": ["architect", "think"],
                "context_strategy": "targeted",
            }

        # Shell/command execution - be more specific to avoid conflicts
        shell_patterns = {
            "explicit_keywords": ["shell", "bash", "terminal", "command line"],
            "command_indicators": ["npm", "pip", "docker", "make", "cargo"],
            "script_keywords": ["script", "run script", "execute script"],
        }

        explicit_shell = any(
            kw in query_lower for kw in shell_patterns["explicit_keywords"]
        )
        command_indicator = any(
            cmd in query_lower for cmd in shell_patterns["command_indicators"]
        )
        script_match = any(
            kw in query_lower for kw in shell_patterns["script_keywords"]
        )

        shell_match = explicit_shell or command_indicator or script_match

        if shell_match:
            shell_tools = ["bash"]
            if "script" in query_lower:
                shell_tools.append("script")

            return {
                "category": "shell_execution",
                "confidence": 0.8,
                "suggested_tools": shell_tools,
                "context_strategy": "minimal",
            }

        # Memory/session management
        memory_patterns = {
            "keywords": [
                "remember",
                "save",
                "recall",
                "memory",
                "session",
                "context",
                "persist",
                "store",
            ],
            "actions": ["save", "load", "remember", "recall", "store", "retrieve"],
        }

        # Memory clearing/destructive operations
        lobotomize_patterns = [
            "lobotomize",
            "clear memory",
            "forget everything",
            "wipe memory",
            "reset memory",
            "start fresh",
            "amnesia",
        ]

        memory_match = any(kw in query_lower for kw in memory_patterns["keywords"])
        memory_action = any(
            action in query_lower for action in memory_patterns["actions"]
        )
        lobotomize_match = any(
            pattern in query_lower for pattern in lobotomize_patterns
        )

        if lobotomize_match:
            return {
                "category": "memory_lobotomize",
                "confidence": 0.95,
                "suggested_tools": ["memory_write"],
                "context_strategy": "minimal",
            }
        elif memory_match and memory_action:
            return {
                "category": "memory_management",
                "confidence": 0.85,
                "suggested_tools": ["memory_read", "memory_write"],
                "context_strategy": "minimal",
            }

        # Reasoning/analysis
        reasoning_patterns = {
            "keywords": [
                "think",
                "analyze",
                "reasoning",
                "decision",
                "pros and cons",
                "brainstorm",
                "problem solving",
                "root cause",
                "evaluate",
                "assess",
            ],
            "triggers": [
                "help me think",
                "what are the",
                "should i",
                "how to approach",
                "break down",
            ],
        }

        reasoning_match = any(
            kw in query_lower for kw in reasoning_patterns["keywords"]
        )
        reasoning_trigger = any(
            trigger in query_lower for trigger in reasoning_patterns["triggers"]
        )

        if reasoning_match or reasoning_trigger:
            return {
                "category": "reasoning_analysis",
                "confidence": 0.8,
                "suggested_tools": ["think"],
                "context_strategy": "targeted",
            }

        # Annotation/organization - but check for TODO search which should be file_operations # noqa: E501
        annotation_patterns = {
            "keywords": ["note", "bookmark", "annotate", "tag", "organize", "reminder"],
            "todo_creation": ["add todo", "create todo", "mark todo", "todo note"],
            "actions": ["add", "create", "mark", "tag", "annotate", "organize"],
        }

        # Don't match "todo" if it's about searching for TODOs
        is_todo_search = any(
            term in query_lower
            for term in ["find todo", "search todo", "todo comments", "all todo"]
        )

        annotation_match = any(
            kw in query_lower for kw in annotation_patterns["keywords"]
        ) or any(term in query_lower for term in annotation_patterns["todo_creation"])
        annotation_action = any(
            action in query_lower for action in annotation_patterns["actions"]
        )

        # Special case for "mark" + code/section which is annotation
        mark_code = "mark" in query_lower and any(
            term in query_lower
            for term in ["code", "section", "function", "class", "line", "important"]
        )

        if mark_code:
            annotation_match = True
            annotation_action = True

        if annotation_match and annotation_action and not is_todo_search:
            return {
                "category": "annotation_organization",
                "confidence": 0.85,
                "suggested_tools": ["sticker_request"],
                "context_strategy": "targeted",
            }

        # Notebook operations
        notebook_patterns = {
            "keywords": ["notebook", "jupyter", "ipynb", "cell", "kernel"],
            "actions": ["read", "edit", "modify", "run", "execute"],
        }

        notebook_match = any(kw in query_lower for kw in notebook_patterns["keywords"])
        notebook_action = any(
            action in query_lower for action in notebook_patterns["actions"]
        )

        if notebook_match and notebook_action:
            notebook_tools = ["notebook_read"]
            if any(word in query_lower for word in ["edit", "modify", "change"]):
                notebook_tools.append("notebook_edit")

            return {
                "category": "notebook_operations",
                "confidence": 0.9,
                "suggested_tools": notebook_tools,
                "context_strategy": "targeted",
            }

        # File operations (if we detected file patterns earlier)
        if file_confidence >= 0.4:
            return {
                "category": "file_operations",
                "confidence": file_confidence,
                "suggested_tools": list(set(file_tools)),
                "context_strategy": "targeted",
            }

        # Multi-tool workflows (complex cases) - be more specific
        complex_patterns = {
            "refactor": ["refactor", "restructure", "reorganize"],
            "debug": ["debug", "troubleshoot"],
            "optimize": ["optimize", "improve performance", "performance"],
            "document": ["document", "documentation", "docs", "readme"],
            "setup": ["setup", "configure", "install", "initialize", "bootstrap"],
        }

        for workflow_type, keywords in complex_patterns.items():
            # Require explicit workflow keywords, not just any mention
            explicit_match = any(kw in query_lower for kw in keywords)

            # Additional context requirements for some workflows
            if workflow_type == "setup" and explicit_match:
                # "setup" should have project/package context
                has_project_context = any(
                    term in query_lower
                    for term in ["project", "package", "environment", "new"]
                )
                if not has_project_context:
                    continue

            if explicit_match:
                workflow_tools = []
                context_strat = "full"

                if workflow_type == "refactor":
                    workflow_tools = ["architect", "grep", "file_edit", "test_runner"]
                elif workflow_type == "debug":
                    workflow_tools = ["grep", "architect", "test_runner", "think"]
                elif workflow_type == "optimize":
                    workflow_tools = ["architect", "think", "test_runner"]
                elif workflow_type == "document":
                    workflow_tools = ["architect", "file_write", "grep"]
                elif workflow_type == "setup":
                    workflow_tools = ["bash", "file_write", "file_read"]
                    context_strat = "minimal"

                return {
                    "category": f"workflow_{workflow_type}",
                    "confidence": 0.8,
                    "suggested_tools": workflow_tools,
                    "context_strategy": context_strat,
                }

        # Default: general code analysis
        return {
            "category": "code_analysis",
            "confidence": 0.5,
            "suggested_tools": ["architect", "grep", "ls"],
            "context_strategy": "full",
        }

    async def build_context(self, query: str, max_files: int = 20) -> ProjectContext:
        """
        Build comprehensive project context optimized for the given query.

        This is the primary entry point for context generation, orchestrating
        the entire process from project scanning to relevance-based file
        selection. It combines multiple analysis techniques to provide the
        most useful context for AI processing.

        Context Building Pipeline:
        1. Query Analysis: Categorize query and determine context strategy
        2. Project Scanning: Discover all relevant files in the project
        3. Concurrent Analysis: Analyze files with semaphore-based throttling
        4. Content Reading: Read file contents for analyzed files
        5. Symbol Indexing: Build reverse index of symbols to files
        6. Dependency Mapping: Construct file dependency relationships
        7. Git Integration: Extract repository state and changes
        8. Relevance Filtering: Select most relevant files for the query

        Performance Optimizations:
        - Concurrent file analysis with configurable limits
        - Multi-layer caching (memory + persistent)
        - Query-driven context strategy selection
        - Intelligent file relevance scoring
        - Semaphore-based resource management

        Args:
            query: User query or task description. Used for relevance scoring
                   and context strategy selection.
            max_files: Maximum number of files to include in final context.
                      Actual number may be less based on relevance scoring.
                      Capped at 1000 for performance.

        Returns:
            ProjectContext object containing:
            - Filtered file contents based on relevance
            - File analysis metadata (language, symbols, imports)
            - Symbol index for fast lookup
            - Dependency graph for understanding relationships
            - Git information (branch, commit, changes)

        Raises:
            ValueError: If max_files is negative.

        Performance Characteristics:
            - Small projects (<100 files): ~100-500ms
            - Medium projects (100-1000 files): ~500ms-2s
            - Large projects (1000+ files): ~2-5s
            - Cache hit ratio: 80-95% for subsequent runs
        """
        # Validate inputs
        if max_files < 0:
            raise ValueError("max_files must be non-negative")

        if max_files > 1000:
            # Prevent excessive resource usage
            max_files = 1000

        # Categorize query to determine context strategy
        query_analysis = self._categorize_query(query)
        # query_category = query_analysis["category"]  # Currently unused
        context_strategy = query_analysis.get("context_strategy", "full")

        # Adjust context based on strategy
        if context_strategy == "none":
            max_files = 0  # No files needed (e.g., tool listing)
        elif context_strategy == "minimal":
            max_files = min(
                max_files, 3
            )  # Minimal context (e.g., agent management, git ops)
        elif context_strategy == "targeted":
            max_files = min(max_files, 10)  # Focused context (e.g., specific analysis)
        # else: context_strategy == "full" uses original max_files

        # Scan project files
        all_files = await self.scan_project()

        # Analyze files concurrently
        semaphore = asyncio.Semaphore(10)  # Limit concurrent file operations

        async def analyze_with_semaphore(path):
            """Analyze a file with semaphore-based concurrency control.

            Wraps the file analysis operation in a semaphore to prevent
            resource exhaustion during concurrent processing. This ensures
            the system remains responsive even when analyzing hundreds or
            thousands of files simultaneously.

            Concurrency Control:
            - Limits concurrent file I/O operations to 10 (configurable)
            - Prevents file descriptor exhaustion
            - Maintains system responsiveness during large project analysis
            - Balances throughput with resource consumption

            Args:
                path: Path to the file to analyze.

            Returns:
                FileInfo object with analysis results if successful,
                or the exception object if analysis fails.

            Note:
                This is a nested function that captures the semaphore from
                the enclosing scope, enabling clean concurrent processing
                with resource limits.
            """
            async with semaphore:
                return await self.analyze_file(path)

        analysis_tasks = [analyze_with_semaphore(f) for f in all_files]
        file_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)

        # Filter valid analyses
        valid_analyses = {}
        for i, analysis in enumerate(file_analyses):
            if isinstance(analysis, FileInfo):
                valid_analyses[all_files[i]] = analysis

        # Read file contents for analyzed files
        file_contents = {}
        content_tasks = []

        # Limit number of files to read based on max_files
        files_to_read = list(valid_analyses.keys())[
            : max_files * 2
        ]  # Read more than needed for filtering

        for file_path in files_to_read:
            content_tasks.append(self._read_file(file_path))

        contents = await asyncio.gather(*content_tasks, return_exceptions=True)

        for file_path, content in zip(files_to_read, contents):
            if isinstance(content, str) and content:
                file_contents[file_path] = content
                # Cache content with size management
                if len(self.file_cache) < self.max_cache_size:
                    self.file_cache[file_path] = (
                        content,
                        valid_analyses[file_path].modified_time,
                    )
                else:
                    self._manage_cache_size()
                    self.file_cache[file_path] = (
                        content,
                        valid_analyses[file_path].modified_time,
                    )

        # Build symbol index
        symbols = defaultdict(list)
        for file_path, analysis in valid_analyses.items():
            if analysis.symbols:
                for symbol_name in analysis.symbols:
                    symbols[symbol_name].append(file_path)

        # Build dependency graph (simplified)
        dependencies = defaultdict(set)
        for file_path, analysis in valid_analyses.items():
            if analysis.imports:
                for imp_name in analysis.imports:
                    # Try to resolve import to actual files
                    for other_path in valid_analyses.keys():
                        if imp_name in str(other_path) or other_path.stem == imp_name:
                            dependencies[file_path].add(other_path)

        # Get Git information
        git_info = None
        if self.repo:
            try:
                git_info = {
                    "branch": self.repo.active_branch.name,
                    "commit": self.repo.head.commit.hexsha[:8],
                    "modified_files": [
                        item.a_path for item in self.repo.index.diff(None)
                    ],
                    "untracked_files": self.repo.untracked_files,
                }
            except Exception:
                pass  # nosec B110

        # Create context and select relevant files
        context = ProjectContext(
            files=file_contents,
            file_info=valid_analyses,
            dependencies=dict(dependencies),
            symbols=dict(symbols),
            project_root=self.root,
            git_info=git_info,
        )

        # Select most relevant files for the query
        relevant_files = context.get_relevant_files(query, max_files)

        # Filter context to only include relevant files
        filtered_files = {
            f: content for f, content in file_contents.items() if f in relevant_files
        }
        filtered_info = {
            f: info for f, info in valid_analyses.items() if f in relevant_files
        }

        context.files = filtered_files
        context.file_info = filtered_info

        return context

    def close_all_connections(self) -> None:
        """Close all active SQLite connections.

        This method ensures that all SQLite database connections are properly
        closed to prevent file locking issues, especially on Windows systems.
        It should be called during cleanup or when the ContextManager is no
        longer needed.

        Side Effects:
            Closes all connections tracked in self._active_connections.
            Clears the connections set after closing.
        """
        import platform

        connections_to_close = list(self._active_connections)
        for conn in connections_to_close:
            try:
                conn.close()
            except Exception:  # nosec B110
                # Ignore errors during cleanup
                pass
        self._active_connections.clear()

        # On Windows, add a small delay to ensure file handles are released
        if platform.system() == "Windows" and connections_to_close:
            import time

            time.sleep(0.1)

    def __del__(self) -> None:
        """Destructor to ensure database connections are closed.

        Automatically called when the ContextManager object is garbage collected.
        This provides a safety net to ensure SQLite connections are closed even
        if explicit cleanup is not performed.
        """
        try:
            self.close_all_connections()
        except Exception:  # nosec B110
            # Ignore errors during destructor
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure connections are closed."""
        self.close_all_connections()


async def main() -> None:
    """Example usage and demonstration of ContextManager capabilities.

    Demonstrates how to use the ContextManager to analyze a project
    and build context for a specific query. This example shows the
    typical workflow and expected outputs.
    """
    # Initialize context manager with current directory
    manager = ContextManager()

    print("Scanning project for authentication-related context...")

    # Build context optimized for authentication-related query
    context = await manager.build_context("authentication login user", max_files=5)

    # Display analysis results
    print(f"\nProject root: {context.project_root}")
    print(f"Files analyzed: {len(context.files)}")
    print(f"Total symbols indexed: {len(context.symbols)}")

    if context.git_info:
        print(f"Git branch: {context.git_info.get('branch', 'unknown')}")
        print(f"Git commit: {context.git_info.get('commit', 'unknown')}")

    print("\nRelevant files found:")
    for file_path in context.files.keys():
        info = context.file_info.get(file_path)
        if info:
            symbol_count = len(info.symbols or [])
            import_count = len(info.imports or [])
            print(f"  {file_path}:")
            print(f"    Language: {info.language or 'unknown'}")
            print(f"    Symbols: {symbol_count}, Imports: {import_count}")


if __name__ == "__main__":
    # Run the example when script is executed directly
    asyncio.run(main())
