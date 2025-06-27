"""
Prompt Repository - Extensible storage and retrieval system for prompt components.

This module provides a scalable solution for managing large collections of
prompt examples, templates, and components. It supports:
- Database-backed storage for thousands of examples
- Dynamic example selection based on similarity
- Version control for prompt evolution
- A/B testing support for prompt optimization
"""

import hashlib
import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional imports for advanced similarity features
try:
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class PromptExample:
    """Represents a single prompt example with metadata."""

    id: str
    query: str
    response: Dict[str, Any]
    category: str
    tags: List[str]
    performance_score: float = 1.0
    usage_count: int = 0
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_used is None:
            self.last_used = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["last_used"] = self.last_used.isoformat() if self.last_used else None
        data["response"] = json.dumps(self.response)
        data["tags"] = json.dumps(self.tags)
        return data


@dataclass
class PromptComponent:
    """Represents a reusable prompt component with versioning."""

    name: str
    content: str
    component_type: str  # system, analysis, workflow, etc.
    version: int = 1
    active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.metadata is None:
            self.metadata = {}


class ExampleStore(ABC):
    """Abstract base class for example storage backends."""

    @abstractmethod
    def add_example(self, example: PromptExample) -> str:
        """Add a new example to the store."""
        pass

    @abstractmethod
    def get_examples(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PromptExample]:
        """Retrieve examples based on filters."""
        pass

    @abstractmethod
    def search_similar(self, query: str, limit: int = 5) -> List[PromptExample]:
        """Find examples similar to the given query."""
        pass

    @abstractmethod
    def update_performance(self, example_id: str, score: float):
        """Update the performance score of an example."""
        pass


class SQLiteExampleStore(ExampleStore):
    """SQLite-backed storage for prompt examples."""

    def __init__(self, db_path: Path):
        """Initialize SQLite store with database path."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS examples (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    performance_score REAL DEFAULT 1.0,
                    usage_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used TEXT NOT NULL,
                    embedding BLOB
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_category ON examples(category)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_performance
                ON examples(performance_score)
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    component_type TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    active BOOLEAN DEFAULT 1,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name, version)
                )
            """
            )

    def add_example(self, example: PromptExample) -> str:
        """Add a new example to the database."""
        if not example.id:
            # Generate ID from query hash
            example.id = hashlib.md5(
                example.query.encode()
            ).hexdigest()[:12]

        with sqlite3.connect(self.db_path) as conn:
            data = example.to_dict()
            conn.execute(
                """
                INSERT OR REPLACE INTO examples
                (id, query, response, category, tags, performance_score,
                 usage_count, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["query"],
                    data["response"],
                    data["category"],
                    data["tags"],
                    data["performance_score"],
                    data["usage_count"],
                    data["created_at"],
                    data["last_used"],
                ),
            )

        return example.id

    def get_examples(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PromptExample]:
        """Retrieve examples based on filters."""
        query = "SELECT * FROM examples WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if tags:
            # Simple tag matching - could be improved with full-text search
            tag_conditions = " AND ".join(["tags LIKE ?" for _ in tags])
            query += f" AND ({tag_conditions})"
            params.extend([f"%{tag}%" for tag in tags])

        query += " ORDER BY performance_score DESC, usage_count DESC LIMIT ?"
        params.append(str(limit))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            examples = []
            for row in cursor:
                example = PromptExample(
                    id=row["id"],
                    query=row["query"],
                    response=json.loads(row["response"]),
                    category=row["category"],
                    tags=json.loads(row["tags"]),
                    performance_score=row["performance_score"],
                    usage_count=row["usage_count"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_used=datetime.fromisoformat(row["last_used"]),
                )
                examples.append(example)

        return examples

    def search_similar(self, query: str, limit: int = 5) -> List[PromptExample]:
        """Find examples similar to the given query using simple text matching."""
        # For now, use simple keyword matching
        # In production, this would use embeddings and vector similarity
        keywords = query.lower().split()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Build query with keyword matching
            # For each keyword, count how many match
            # nosec B608 - SQL is constructed from safe parameterized components
            conditions = " OR ".join(["query LIKE ?" for _ in keywords])
            
            # Build match count expression
            match_counts = []
            for i, kw in enumerate(keywords):
                match_counts.append("(CASE WHEN query LIKE ? THEN 1 ELSE 0 END)")
            
            match_count_expr = " + ".join(match_counts) if match_counts else "0"
            
            # nosec B608 - SQL is constructed from safe parameterized components
            query_sql = f"""
                SELECT *,
                ({match_count_expr}) as match_count
                FROM examples
                WHERE {conditions}
                ORDER BY match_count DESC, performance_score DESC
                LIMIT ?
            """

            # Parameters: match count checks, then WHERE conditions, then limit
            params = [f"%{kw}%" for kw in keywords]  # for match count
            params += [f"%{kw}%" for kw in keywords]  # for WHERE clause
            params += [str(limit)]
            
            cursor = conn.execute(query_sql, params)

            examples = []
            for row in cursor:
                example = PromptExample(
                    id=row["id"],
                    query=row["query"],
                    response=json.loads(row["response"]),
                    category=row["category"],
                    tags=json.loads(row["tags"]),
                    performance_score=row["performance_score"],
                    usage_count=row["usage_count"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_used=datetime.fromisoformat(row["last_used"]),
                )
                examples.append(example)

        return examples

    def update_performance(self, example_id: str, score: float):
        """Update the performance score of an example."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE examples
                SET performance_score = ?,
                    usage_count = usage_count + 1,
                    last_used = ?
                WHERE id = ?
            """,
                (score, datetime.now().isoformat(), example_id),
            )

    def add_component(self, component: PromptComponent) -> int:
        """Add or update a prompt component."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if component exists
            query = (
                "SELECT id, version FROM components WHERE name = ? "
                "ORDER BY version DESC LIMIT 1"
            )
            existing = conn.execute(query, (component.name,)).fetchone()

            if existing:
                component.version = existing[1] + 1

            cursor = conn.execute(
                """
                INSERT INTO components
                (
                    name,
                    content,
                    component_type,
                    version,
                    active,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    component.name,
                    component.content,
                    component.component_type,
                    component.version,
                    component.active,
                    json.dumps(component.metadata),
                    component.created_at.isoformat() if component.created_at else None,
                    component.updated_at.isoformat() if component.updated_at else None,
                ),
            )

            # Deactivate previous versions
            if existing:
                query = (
                    "UPDATE components SET active = 0 WHERE name = ? AND version < ?"
                )
                conn.execute(query, (component.name, component.version))

            return cursor.lastrowid or 0

    def get_component(
        self, name: str, version: Optional[int] = None
    ) -> Optional[PromptComponent]:
        """Get a prompt component by name and optional version."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if version:
                cursor = conn.execute(
                    "SELECT * FROM components WHERE name = ? AND version = ?",
                    (name, version),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM components WHERE name = ? AND active = 1", (name,)
                )

            row = cursor.fetchone()
            if row:
                return PromptComponent(
                    name=row["name"],
                    content=row["content"],
                    component_type=row["component_type"],
                    version=row["version"],
                    active=bool(row["active"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )

        return None


class PromptRepository:
    """High-level interface for managing prompts and examples."""

    def __init__(self, storage_path: Path):
        """Initialize repository with storage backend."""
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize stores
        self.example_store = SQLiteExampleStore(storage_path / "examples.db")

        # Cache for frequently used components
        self._component_cache: Dict[str, PromptComponent] = {}

    def add_examples_from_file(self, file_path: Path, category: str):
        """Import examples from a markdown or JSON file."""
        content = file_path.read_text()

        if file_path.suffix == ".json":
            examples_data = json.loads(content)
        else:
            # Parse markdown format
            examples_data = self._parse_markdown_examples(content)

        for example_data in examples_data:
            example = PromptExample(
                id="",  # Will be generated
                query=example_data["query"],
                response=example_data["response"],
                category=category,
                tags=example_data.get("tags", []),
            )
            self.example_store.add_example(example)

    def _parse_markdown_examples(self, content: str) -> List[Dict[str, Any]]:
        """Parse examples from markdown format."""
        examples = []
        lines = content.strip().split("\n")

        i = 0
        while i < len(lines):
            if lines[i].startswith("Query:"):
                query = lines[i][6:].strip().strip('"')
                i += 1

                if i < len(lines) and lines[i].startswith("Response:"):
                    response_line = lines[i][9:].strip()
                    try:
                        response = json.loads(response_line)
                    except Exception:
                        response = {"raw": response_line}

                    examples.append({"query": query, "response": response, "tags": []})
            i += 1

        return examples

    def get_examples_for_prompt(
        self, query: str, category: Optional[str] = None, strategy: str = "similar"
    ) -> List[PromptExample]:
        """Get relevant examples for building a prompt.

        Strategies:
        - similar: Find examples similar to the query
        - diverse: Get diverse examples covering different cases
        - performance: Get highest performing examples
        """
        if strategy == "similar":
            return self.example_store.search_similar(query, limit=5)
        elif strategy == "diverse":
            # Get examples from different categories
            categories = ["tool_use", "knowledge", "complex", "error"]
            examples = []
            for cat in categories:
                examples.extend(self.example_store.get_examples(category=cat, limit=2))
            return examples[:8]
        else:  # performance
            return self.example_store.get_examples(category=category, limit=10)

    def update_component(self, name: str, content: str, component_type: str):
        """Update a prompt component with versioning."""
        component = PromptComponent(
            name=name, content=content, component_type=component_type
        )
        self.example_store.add_component(component)

        # Update cache
        self._component_cache[name] = component

    def get_component(self, name: str) -> Optional[str]:
        """Get the content of a prompt component."""
        if name in self._component_cache:
            return self._component_cache[name].content

        component = self.example_store.get_component(name)
        if component:
            self._component_cache[name] = component
            return component.content

        return None

    def track_example_performance(self, example_id: str, success: bool):
        """Track the performance of an example."""
        # Simple scoring: successful use increases score, failure decreases
        score = 1.1 if success else 0.9
        self.example_store.update_performance(example_id, score)


# Example usage for migrating existing examples
def migrate_existing_examples():
    """Migrate examples from markdown files to the repository."""
    repo = PromptRepository(Path("ocode_python/prompts/data"))

    # Load existing examples
    examples_file = Path("ocode_python/prompts/analysis/tool_examples.md")
    if examples_file.exists():
        repo.add_examples_from_file(examples_file, "tool_decision")

    # Add programmatically generated examples
    common_queries = [
        (
            "fix the bug in main.py",
            {"should_use_tools": True, "suggested_tools": ["file_read", "file_edit"]},
        ),
        ("what is recursion", {"should_use_tools": False, "suggested_tools": []}),
        (
            "analyze project structure",
            {"should_use_tools": True, "suggested_tools": ["architect", "find"]},
        ),
        # ... hundreds more examples
    ]

    for query, response in common_queries:
        example = PromptExample(
            id="",
            query=query,
            response=response,
            category="tool_decision",
            tags=["common"],
        )
        repo.example_store.add_example(example)
