"""
Semantic context selection using embeddings and intelligent relevance.

This module implements advanced semantic analysis for better context selection,
including embedding-based similarity, dynamic context expansion, and dependency
following.
"""

import hashlib
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    # Try to import sentence-transformers for semantic embeddings
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    # Fallback to basic semantic analysis
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None

import numpy as np

from .context_manager import ContextManager, ProjectContext


@dataclass
class SemanticFile:
    """File with semantic information."""

    path: Path
    content: str
    embedding: Optional[np.ndarray] = None
    similarity_score: float = 0.0
    dependency_score: float = 0.0
    frequency_score: float = 0.0
    final_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextExpansionRule:
    """Rule for expanding context based on dependencies."""

    rule_name: str
    trigger_pattern: str  # Regex pattern to match in query
    expansion_type: str  # 'imports', 'callers', 'tests', 'config'
    max_expansion: int = 5
    weight: float = 1.0


class EmbeddingCache:
    """Cache for file embeddings with persistence."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "embeddings.db"
        self._init_db()
        self.memory_cache: Dict[str, np.ndarray] = {}
        self.max_memory_cache = 1000

    def _init_db(self) -> None:
        """Initialize the embeddings database."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT,
                    embedding BLOB,
                    model_version TEXT,
                    created_at REAL
                )
            """
            )
            conn.commit()
        finally:
            conn.close()

    def get_embedding(
        self, file_path: str, content_hash: str, model_version: str
    ) -> Optional[np.ndarray]:
        """Get cached embedding for a file."""
        # Check memory cache first
        cache_key = f"{file_path}:{content_hash}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]

        # Check persistent cache
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT embedding FROM embeddings
                WHERE file_path = ? AND content_hash = ? AND model_version = ?
            """,
                (file_path, content_hash, model_version),
            )

            row = cursor.fetchone()
            if row:
                embedding = np.frombuffer(row[0], dtype=np.float32)

                # Add to memory cache
                if len(self.memory_cache) < self.max_memory_cache:
                    self.memory_cache[cache_key] = embedding

                return embedding

        except sqlite3.Error as e:
            logging.warning(f"Error reading embedding cache: {e}")
        finally:
            conn.close()

        return None

    def store_embedding(
        self,
        file_path: str,
        content_hash: str,
        embedding: np.ndarray,
        model_version: str,
    ) -> None:
        """Store embedding in cache."""
        # Store in memory cache
        cache_key = f"{file_path}:{content_hash}"
        if len(self.memory_cache) < self.max_memory_cache:
            self.memory_cache[cache_key] = embedding

        # Store in persistent cache
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO embeddings
                (file_path, content_hash, embedding, model_version, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    file_path,
                    content_hash,
                    embedding.tobytes(),
                    model_version,
                    time.time(),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logging.warning(f"Error storing embedding cache: {e}")
        finally:
            conn.close()


class SemanticContextBuilder:
    """Advanced context builder using semantic analysis."""

    def __init__(
        self, context_manager: ContextManager, cache_dir: Optional[Path] = None
    ):
        self.context_manager = context_manager
        self.cache_dir = cache_dir or (context_manager.cache_dir / "semantic")
        self.embedding_cache = EmbeddingCache(self.cache_dir)

        # Initialize embedding model if available
        self.embeddings_model = None
        self.model_version = "fallback"

        if EMBEDDINGS_AVAILABLE:
            try:
                self.embeddings_model = SentenceTransformer("all-MiniLM-L6-v2")
                self.model_version = "all-MiniLM-L6-v2"
                logging.info("Semantic embeddings enabled with sentence-transformers")
            except Exception as e:
                logging.warning(f"Failed to load embedding model: {e}")
                # Note: Cannot modify global EMBEDDINGS_AVAILABLE from here

        # Context expansion rules
        self.expansion_rules = [
            ContextExpansionRule(
                rule_name="import_following",
                trigger_pattern=r"import|from|include|require",
                expansion_type="imports",
                max_expansion=5,
                weight=0.8,
            ),
            ContextExpansionRule(
                rule_name="test_files",
                trigger_pattern=r"test|spec|unittest",
                expansion_type="tests",
                max_expansion=10,
                weight=0.9,
            ),
            ContextExpansionRule(
                rule_name="config_files",
                trigger_pattern=r"config|settings|env",
                expansion_type="config",
                max_expansion=5,
                weight=0.7,
            ),
        ]

    async def build_semantic_context(
        self, query: str, files: Dict[Path, str], max_files: int = 20
    ) -> List[SemanticFile]:
        """Build context using semantic similarity and intelligent scoring."""
        if not files:
            return []

        # Convert to semantic files
        semantic_files = []
        for file_path, content in files.items():
            # Ensure file_path is a Path object
            if isinstance(file_path, str):
                file_path = Path(file_path)
            semantic_file = SemanticFile(
                path=file_path, content=content, metadata={"size": len(content)}
            )
            semantic_files.append(semantic_file)

        # Compute embeddings and similarity scores
        if EMBEDDINGS_AVAILABLE and self.embeddings_model:
            await self._compute_semantic_scores(query, semantic_files)
        else:
            await self._compute_keyword_scores(query, semantic_files)

        # Compute dependency scores
        await self._compute_dependency_scores(semantic_files)

        # Compute frequency scores (how often files are accessed)
        await self._compute_frequency_scores(semantic_files)

        # Combine scores with weights
        for semantic_file in semantic_files:
            semantic_file.final_score = (
                semantic_file.similarity_score * 0.4
                + semantic_file.dependency_score * 0.3
                + semantic_file.frequency_score * 0.2
                + self._compute_path_score(semantic_file.path, query) * 0.1
            )

        # Sort by final score and return top files
        semantic_files.sort(key=lambda x: x.final_score, reverse=True)

        # Apply dynamic context expansion
        expanded_files = await self._apply_context_expansion(
            query, semantic_files[:max_files], files
        )

        return expanded_files[:max_files]

    async def _compute_semantic_scores(
        self, query: str, semantic_files: List[SemanticFile]
    ) -> None:
        """Compute semantic similarity scores using embeddings."""
        if not self.embeddings_model:
            return

        try:
            # Get query embedding
            query_embedding = self.embeddings_model.encode(query)

            # Process files in batches to avoid memory issues
            batch_size = 10
            for i in range(0, len(semantic_files), batch_size):
                batch = semantic_files[i : i + batch_size]
                await self._process_embedding_batch(query_embedding, batch)

        except Exception as e:
            logging.warning(f"Error computing semantic scores: {e}")
            # Fallback to keyword-based scoring
            await self._compute_keyword_scores(query, semantic_files)

    async def _process_embedding_batch(
        self, query_embedding: np.ndarray, batch: List[SemanticFile]
    ) -> None:
        """Process a batch of files for embeddings."""
        texts_to_encode = []
        files_to_encode = []

        for semantic_file in batch:
            content_hash = hashlib.md5(  # nosec B324
                semantic_file.content.encode(), usedforsecurity=False
            ).hexdigest()

            # Check cache first
            cached_embedding = self.embedding_cache.get_embedding(
                str(semantic_file.path), content_hash, self.model_version
            )

            if cached_embedding is not None:
                semantic_file.embedding = cached_embedding
                # Compute similarity with query
                similarity = np.dot(query_embedding, cached_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
                )
                semantic_file.similarity_score = float(similarity)
            else:
                # Need to compute embedding
                # Truncate content to reasonable length for embedding
                content_preview = semantic_file.content[:2000]  # First 2000 chars
                texts_to_encode.append(content_preview)
                files_to_encode.append((semantic_file, content_hash))

        # Compute embeddings for files not in cache
        if texts_to_encode:
            try:
                embeddings = self.embeddings_model.encode(texts_to_encode)

                for i, (semantic_file, content_hash) in enumerate(files_to_encode):
                    embedding = embeddings[i]
                    semantic_file.embedding = embedding

                    # Store in cache
                    self.embedding_cache.store_embedding(
                        str(semantic_file.path),
                        content_hash,
                        embedding,
                        self.model_version,
                    )

                    # Compute similarity
                    similarity = np.dot(query_embedding, embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                    )
                    semantic_file.similarity_score = float(similarity)

            except Exception as e:
                logging.warning(f"Error encoding batch: {e}")

    async def _compute_keyword_scores(
        self, query: str, semantic_files: List[SemanticFile]
    ) -> None:
        """Fallback keyword-based similarity scoring."""
        query_words = set(query.lower().split())

        for semantic_file in semantic_files:
            content_words = set(semantic_file.content.lower().split())

            if query_words and content_words:
                intersection = query_words.intersection(content_words)
                union = query_words.union(content_words)
                jaccard_similarity = len(intersection) / len(union) if union else 0
                semantic_file.similarity_score = jaccard_similarity
            else:
                semantic_file.similarity_score = 0.0

    async def _compute_dependency_scores(
        self, semantic_files: List[SemanticFile]
    ) -> None:
        """Compute scores based on file dependencies."""
        # Build dependency graph
        import_graph: Dict[str, Set[str]] = {}

        for semantic_file in semantic_files:
            file_key = str(semantic_file.path)
            import_graph[file_key] = set()

            # Extract imports (simple pattern matching)
            file_suffix = (
                semantic_file.path.suffix
                if hasattr(semantic_file.path, "suffix")
                else Path(semantic_file.path).suffix
            )
            imports = self._extract_imports(semantic_file.content, file_suffix)

            for imp in imports:
                # Try to resolve import to actual files
                for other_file in semantic_files:
                    if (
                        imp in str(other_file.path)
                        or other_file.path.stem == imp
                        or imp in other_file.content
                    ):
                        import_graph[file_key].add(str(other_file.path))

        # Calculate dependency scores
        for semantic_file in semantic_files:
            file_key = str(semantic_file.path)

            # Score based on how many files depend on this one
            dependents = sum(
                1 for imports in import_graph.values() if file_key in imports
            )

            # Score based on how many files this one depends on
            dependencies = len(import_graph.get(file_key, set()))

            # Normalize and combine
            max_dependents = len(semantic_files)
            semantic_file.dependency_score = (dependents / max_dependents) * 0.7 + (
                min(dependencies, 10) / 10
            ) * 0.3

    def _extract_imports(self, content: str, file_extension: str) -> List[str]:
        """Extract import statements from file content."""
        imports = []
        lines = content.split("\n")

        if file_extension == ".py":
            import re

            for line in lines:
                # Python imports
                match = re.match(r"^\s*(?:from\s+(\S+)\s+)?import\s+(\S+)", line)
                if match:
                    module = match.group(1) or match.group(2)
                    imports.append(module.split(".")[0])

        elif file_extension in [".js", ".ts", ".jsx", ".tsx"]:
            import re

            for line in lines:
                # JavaScript/TypeScript imports
                match = re.match(r'^\s*import\s+.*?from\s+["\']([^"\']+)["\']', line)
                if match:
                    module = match.group(1)
                    if module.startswith("./") or module.startswith("../"):
                        # Relative import
                        imports.append(module)
                    else:
                        imports.append(module.split("/")[0])

        return imports

    async def _compute_frequency_scores(
        self, semantic_files: List[SemanticFile]
    ) -> None:
        """Compute scores based on file access frequency."""
        # For now, use simple heuristics based on file characteristics
        for semantic_file in semantic_files:
            score = 0.0

            # Ensure path is a Path object
            if isinstance(semantic_file.path, str):
                semantic_file.path = Path(semantic_file.path)

            # Main files get higher scores
            if semantic_file.path.name in [
                "main.py",
                "index.js",
                "app.py",
                "__init__.py",
            ]:
                score += 0.5

            # Configuration files get medium scores
            if semantic_file.path.suffix in [".json", ".yaml", ".yml", ".toml"]:
                score += 0.3

            # Test files get lower scores unless specifically requested
            if "test" in semantic_file.path.name.lower():
                score += 0.1

            # Larger files might be more important
            size_factor = min(len(semantic_file.content) / 10000, 1.0)  # Cap at 10KB
            score += size_factor * 0.2

            semantic_file.frequency_score = score

    def _compute_path_score(self, file_path: Path, query: str) -> float:
        """Compute score based on path relevance to query."""
        # Ensure file_path is a Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        query_lower = query.lower()
        path_str = str(file_path).lower()

        score = 0.0
        query_words = query_lower.split()

        for word in query_words:
            if word in path_str:
                score += 0.2

            # Higher score for matches in filename
            if word in file_path.name.lower():
                score += 0.5

        return min(score, 1.0)

    async def _apply_context_expansion(
        self, query: str, selected_files: List[SemanticFile], all_files: Dict[Path, str]
    ) -> List[SemanticFile]:
        """Apply context expansion rules."""
        import re

        expanded_files = list(selected_files)

        for rule in self.expansion_rules:
            if re.search(rule.trigger_pattern, query, re.IGNORECASE):
                additional_files = await self._expand_by_rule(
                    rule, selected_files, all_files
                )

                # Add additional files with reduced scores
                for additional_file in additional_files[: rule.max_expansion]:
                    additional_file.final_score *= rule.weight
                    # Check if file is already in expanded_files by path
                    if not any(
                        ef.path == additional_file.path for ef in expanded_files
                    ):
                        expanded_files.append(additional_file)

        return expanded_files

    async def _expand_by_rule(
        self,
        rule: ContextExpansionRule,
        selected_files: List[SemanticFile],
        all_files: Dict[Path, str],
    ) -> List[SemanticFile]:
        """Expand context based on a specific rule."""
        if rule.expansion_type == "imports":
            return self._expand_by_imports(selected_files, all_files)
        elif rule.expansion_type == "tests":
            return self._expand_by_tests(selected_files, all_files)
        elif rule.expansion_type == "config":
            return self._expand_by_config(all_files)
        return []

    def _expand_by_imports(
        self, selected_files: List[SemanticFile], all_files: Dict[Path, str]
    ) -> List[SemanticFile]:
        """Expand context by following import chains."""
        additional_files = []
        for semantic_file in selected_files:
            imports = self._extract_imports(
                semantic_file.content, semantic_file.path.suffix
            )
            for imp in imports:
                for file_path, content in all_files.items():
                    if isinstance(file_path, str):
                        file_path = Path(file_path)
                    if imp in str(file_path) or file_path.stem == imp:
                        additional_file = SemanticFile(
                            path=file_path,
                            content=content,
                            similarity_score=0.5,
                            dependency_score=0.8,
                            frequency_score=0.3,
                        )
                        additional_files.append(additional_file)
        return additional_files

    def _expand_by_tests(
        self, selected_files: List[SemanticFile], all_files: Dict[Path, str]
    ) -> List[SemanticFile]:
        """Expand context by finding related test files."""
        additional_files = []
        for semantic_file in selected_files:
            stem = semantic_file.path.stem
            for file_path, content in all_files.items():
                if isinstance(file_path, str):
                    file_path = Path(file_path)
                if "test" in file_path.name.lower() and stem in file_path.name.lower():
                    additional_file = SemanticFile(
                        path=file_path,
                        content=content,
                        similarity_score=0.6,
                        dependency_score=0.5,
                        frequency_score=0.4,
                    )
                    additional_files.append(additional_file)
        return additional_files

    def _expand_by_config(self, all_files: Dict[Path, str]) -> List[SemanticFile]:
        """Expand context by finding configuration files."""
        additional_files = []
        config_extensions = {".json", ".yaml", ".yml", ".toml", ".ini", ".env"}
        for file_path, content in all_files.items():
            if isinstance(file_path, str):
                file_path = Path(file_path)
            if (
                file_path.suffix in config_extensions
                or "config" in file_path.name.lower()
            ):
                additional_file = SemanticFile(
                    path=file_path,
                    content=content,
                    similarity_score=0.4,
                    dependency_score=0.3,
                    frequency_score=0.6,
                )
                additional_files.append(additional_file)
        return additional_files

    def get_context_breadcrumbs(self, selected_files: List[SemanticFile]) -> List[str]:
        """Generate context breadcrumbs showing relevance chain."""
        breadcrumbs = []

        for semantic_file in selected_files:
            breadcrumb = (
                f"{semantic_file.path.name} (score: {semantic_file.final_score:.2f}"
            )

            details = []
            if semantic_file.similarity_score > 0.3:
                details.append(f"semantic: {semantic_file.similarity_score:.2f}")
            if semantic_file.dependency_score > 0.3:
                details.append(f"deps: {semantic_file.dependency_score:.2f}")
            if semantic_file.frequency_score > 0.3:
                details.append(f"freq: {semantic_file.frequency_score:.2f}")

            if details:
                breadcrumb += f", {', '.join(details)}"

            breadcrumb += ")"
            breadcrumbs.append(breadcrumb)

        return breadcrumbs


class DynamicContextManager:
    """Enhanced context manager with dynamic expansion capabilities."""

    def __init__(self, base_context_manager: ContextManager):
        self.base_context_manager = base_context_manager
        self.semantic_builder = SemanticContextBuilder(base_context_manager)
        self.context_history: List[Dict[str, Any]] = []
        self.expansion_cache: Dict[str, List[Path]] = {}

    async def build_dynamic_context(
        self, query: str, initial_max_files: int = 10, expansion_factor: float = 1.5
    ) -> ProjectContext:
        """Build context that can dynamically expand based on needs."""
        # Start with minimal context
        base_context = await self.base_context_manager.build_context(
            query, max_files=initial_max_files
        )

        # Apply semantic analysis
        semantic_files = await self.semantic_builder.build_semantic_context(
            query,
            base_context.files,
            max_files=int(initial_max_files * expansion_factor),
        )

        # Rebuild context with semantically selected files
        selected_paths = [sf.path for sf in semantic_files]

        # Create enhanced context
        enhanced_files = {}
        enhanced_file_info = {}

        for semantic_file in semantic_files:
            enhanced_files[semantic_file.path] = semantic_file.content
            if semantic_file.path in base_context.file_info:
                enhanced_file_info[semantic_file.path] = base_context.file_info[
                    semantic_file.path
                ]

        enhanced_context = ProjectContext(
            files=enhanced_files,
            file_info=enhanced_file_info,
            dependencies=base_context.dependencies,
            symbols=base_context.symbols,
            project_root=base_context.project_root,
            git_info=base_context.git_info,
        )

        # Store context history for learning
        self.context_history.append(
            {
                "query": query,
                "selected_files": selected_paths,
                "breadcrumbs": self.semantic_builder.get_context_breadcrumbs(
                    semantic_files
                ),
                "timestamp": time.time(),
            }
        )

        return enhanced_context

    async def expand_context_on_demand(
        self,
        current_context: ProjectContext,
        expansion_hint: str,
        max_additional_files: int = 5,
    ) -> ProjectContext:
        """Expand existing context based on runtime needs."""
        cache_key = f"{hash(expansion_hint)}:{len(current_context.files)}"

        if cache_key in self.expansion_cache:
            additional_paths = self.expansion_cache[cache_key]
        else:
            # Scan for additional relevant files
            all_files = await self.base_context_manager.scan_project()
            current_paths = set(current_context.files.keys())
            candidate_files = [f for f in all_files if f not in current_paths]

            # Read candidate files
            candidate_content = {}
            for file_path in candidate_files[:50]:  # Limit for performance
                content = await self.base_context_manager._read_file(file_path)
                if content:
                    candidate_content[file_path] = content

            # Apply semantic selection for expansion
            semantic_files = await self.semantic_builder.build_semantic_context(
                expansion_hint, candidate_content, max_files=max_additional_files
            )

            additional_paths = [sf.path for sf in semantic_files]
            self.expansion_cache[cache_key] = additional_paths

        # Add additional files to context
        expanded_files = dict(current_context.files)
        expanded_file_info = dict(current_context.file_info)

        for file_path in additional_paths:
            if file_path not in expanded_files:
                content = await self.base_context_manager._read_file(file_path)
                if content:
                    expanded_files[file_path] = content

                    # Analyze the file
                    file_info = await self.base_context_manager.analyze_file(file_path)
                    if file_info:
                        expanded_file_info[file_path] = file_info

        # Return expanded context
        return ProjectContext(
            files=expanded_files,
            file_info=expanded_file_info,
            dependencies=current_context.dependencies,
            symbols=current_context.symbols,
            project_root=current_context.project_root,
            git_info=current_context.git_info,
        )

    def get_context_insights(self) -> Dict[str, Any]:
        """Get insights about context selection patterns."""
        if not self.context_history:
            return {}

        recent_queries = [entry["query"] for entry in self.context_history[-10:]]
        frequent_files = {}

        for entry in self.context_history:
            for file_path in entry["selected_files"]:
                file_key = str(file_path)
                frequent_files[file_key] = frequent_files.get(file_key, 0) + 1

        return {
            "total_contexts": len(self.context_history),
            "recent_queries": recent_queries,
            "most_frequent_files": sorted(
                frequent_files.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "cache_hits": len(self.expansion_cache),
            "embeddings_enabled": EMBEDDINGS_AVAILABLE,
        }
