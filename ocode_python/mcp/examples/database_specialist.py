#!/usr/bin/env python3
"""
Example Database Specialist MCP Server.

This demonstrates how to create a specialized MCP server for database operations.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from ocode_python.mcp.protocol import MCPPrompt, MCPResource, MCPServer, MCPTool

logger = logging.getLogger(__name__)


class DatabaseSpecialist(MCPServer):
    """Database specialist MCP server with SQL expertise."""

    def __init__(self, auth_token: Optional[str] = None):
        """Initialize the database specialist."""
        super().__init__(
            name="Database Specialist",
            version="1.0.0",
        )

        # Register capabilities
        self._register_resources()
        self._register_tools()
        self._register_prompts()

    def _register_resources(self):
        """Register database-related resources."""
        # Best practices document
        self.register_resource(
            MCPResource(
                uri="db://best-practices/indexing",
                name="Database Indexing Best Practices",
                description="Guidelines for optimal database indexing strategies",
                mime_type="text/markdown",
            )
        )

        # SQL patterns
        self.register_resource(
            MCPResource(
                uri="db://patterns/common-queries",
                name="Common SQL Query Patterns",
                description="Frequently used SQL query patterns and optimizations",
                mime_type="text/markdown",
            )
        )

        # Schema design guide
        self.register_resource(
            MCPResource(
                uri="db://guides/schema-design",
                name="Database Schema Design Guide",
                description="Best practices for designing database schemas",
                mime_type="text/markdown",
            )
        )

    def _register_tools(self):
        """Register database tools."""
        # SQL formatter tool
        self.register_tool(
            MCPTool(
                name="format_sql",
                description="Format and beautify SQL queries for better readability",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to format",
                        },
                        "dialect": {
                            "type": "string",
                            "enum": ["postgresql", "mysql", "sqlite", "sqlserver"],
                            "default": "postgresql",
                            "description": "SQL dialect for formatting",
                        },
                    },
                    "required": ["query"],
                },
            )
        )

        # Query analyzer tool
        self.register_tool(
            MCPTool(
                name="analyze_query",
                description=(
                    "Analyze SQL query for performance issues and optimizations"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to analyze",
                        },
                        "schema": {
                            "type": "object",
                            "description": "Optional database schema for analysis",
                            "properties": {
                                "tables": {
                                    "type": "object",
                                    "description": "Table definitions",
                                }
                            },
                        },
                    },
                    "required": ["query"],
                },
            )
        )

        # Schema validator tool
        self.register_tool(
            MCPTool(
                name="validate_schema",
                description="Validate database schema design and suggest improvements",
                input_schema={
                    "type": "object",
                    "properties": {
                        "schema": {
                            "type": "object",
                            "description": "Database schema to validate",
                        }
                    },
                    "required": ["schema"],
                },
            )
        )

    def _register_prompts(self):
        """Register database-related prompts."""
        # Query optimization prompt
        self.register_prompt(
            MCPPrompt(
                name="optimize_query",
                description="Guide for optimizing database queries",
                arguments=[
                    {
                        "name": "query",
                        "description": "The SQL query to optimize",
                        "required": True,
                    },
                    {
                        "name": "performance_metrics",
                        "description": "Current performance metrics (time, rows, etc.)",
                        "required": False,
                    },
                ],
            )
        )

        # Schema design prompt
        self.register_prompt(
            MCPPrompt(
                name="design_schema",
                description="Guide for designing a database schema",
                arguments=[
                    {
                        "name": "requirements",
                        "description": "Business requirements for the database",
                        "required": True,
                    },
                    {
                        "name": "constraints",
                        "description": (
                            "Technical constraints (performance, scale, etc.)"
                        ),
                        "required": False,
                    },
                ],
            )
        )

    async def start(self):
        """Start the MCP server and register handlers."""
        # Register resource handlers
        self.set_resource_handler(
            "db://best-practices/indexing", self._get_indexing_guide
        )
        self.set_resource_handler(
            "db://patterns/common-queries", self._get_query_patterns
        )
        self.set_resource_handler("db://guides/schema-design", self._get_schema_guide)

        # Register tool handlers
        self.set_tool_handler("format_sql", self._format_sql)
        self.set_tool_handler("analyze_query", self._analyze_query)
        self.set_tool_handler("validate_schema", self._validate_schema)

        # Register prompt handlers
        self.set_prompt_handler("optimize_query", self._optimize_query_prompt)
        self.set_prompt_handler("design_schema", self._design_schema_prompt)

        logger.info("Database Specialist MCP Server started")

    # Resource handlers

    async def _get_indexing_guide(self) -> str:
        """Return database indexing best practices."""
        return """# Database Indexing Best Practices

## When to Create Indexes

1. **Primary Keys**: Always indexed automatically
2. **Foreign Keys**: Index columns used in JOIN operations
3. **WHERE Clauses**: Index columns frequently used in WHERE conditions
4. **ORDER BY**: Index columns used for sorting
5. **GROUP BY**: Index columns used for grouping

## Index Types

### B-Tree Indexes (Default)
- Good for: Equality and range queries
- Use when: Most general cases

### Hash Indexes
- Good for: Exact match queries only
- Use when: No range queries needed

### Full-Text Indexes
- Good for: Text search operations
- Use when: Searching within text content

## Best Practices

1. **Avoid Over-Indexing**: Each index slows down writes
2. **Column Order Matters**: Most selective columns first
3. **Monitor Index Usage**: Remove unused indexes
4. **Consider Covering Indexes**: Include all query columns
5. **Partial Indexes**: Index only relevant rows

## Anti-Patterns to Avoid

- Indexing low-cardinality columns (e.g., boolean)
- Too many indexes on frequently updated tables
- Redundant indexes (already covered by another index)
- Not maintaining index statistics
"""

    async def _get_query_patterns(self) -> str:
        """Return common SQL query patterns."""
        return """# Common SQL Query Patterns

## Pagination

```sql
-- Offset-based (simple but can be slow for large offsets)
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 10 OFFSET 20;

-- Cursor-based (more efficient)
SELECT * FROM users
WHERE created_at < '2024-01-01'
ORDER BY created_at DESC
LIMIT 10;
```

## Upsert Operations

```sql
-- PostgreSQL
INSERT INTO users (email, name)
VALUES ('user@example.com', 'John')
ON CONFLICT (email)
DO UPDATE SET name = EXCLUDED.name;

-- MySQL
INSERT INTO users (email, name)
VALUES ('user@example.com', 'John')
ON DUPLICATE KEY UPDATE name = VALUES(name);
```

## Window Functions

```sql
-- Running total
SELECT
    date,
    amount,
    SUM(amount) OVER (ORDER BY date) as running_total
FROM transactions;

-- Rank within groups
SELECT
    department,
    employee_name,
    salary,
    RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank
FROM employees;
```

## Common Table Expressions (CTEs)

```sql
WITH monthly_sales AS (
    SELECT
        DATE_TRUNC('month', order_date) as month,
        SUM(total) as total_sales
    FROM orders
    GROUP BY 1
)
SELECT
    month,
    total_sales,
    LAG(total_sales) OVER (ORDER BY month) as prev_month,
    total_sales - LAG(total_sales) OVER (ORDER BY month) as growth
FROM monthly_sales;
```
"""

    async def _get_schema_guide(self) -> str:
        """Return database schema design guide."""
        return """# Database Schema Design Guide

## Normalization Levels

### 1NF (First Normal Form)
- Each column contains atomic values
- No repeating groups

### 2NF (Second Normal Form)
- Meets 1NF
- No partial dependencies on composite keys

### 3NF (Third Normal Form)
- Meets 2NF
- No transitive dependencies

## Design Principles

### 1. Choose Appropriate Data Types
- Use the smallest data type that can accommodate your data
- Consider future growth
- Be consistent across related columns

### 2. Primary Key Selection
- Natural keys vs. Surrogate keys
- UUID vs. Auto-increment
- Composite keys when appropriate

### 3. Relationship Design
- One-to-One: Consider merging tables
- One-to-Many: Foreign key in the "many" table
- Many-to-Many: Junction table with composite key

### 4. Constraint Implementation
- NOT NULL for required fields
- UNIQUE for natural keys
- CHECK constraints for data validation
- Foreign keys for referential integrity

## Performance Considerations

1. **Denormalization**: Strategic duplication for read performance
2. **Partitioning**: Split large tables by date, region, etc.
3. **Archiving**: Move old data to separate tables
4. **Vertical Splitting**: Separate frequently/infrequently accessed columns

## Common Patterns

### Audit Trail
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50),
    record_id INTEGER,
    action VARCHAR(10),
    changed_by INTEGER REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    old_values JSONB,
    new_values JSONB
);
```

### Hierarchical Data
```sql
-- Adjacency List
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    parent_id INTEGER REFERENCES categories(id)
);

-- Materialized Path
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    path VARCHAR(255) -- e.g., '/1/3/7/'
);
```
"""

    # Tool handlers

    async def _format_sql(
        self, query: str, dialect: str = "postgresql"
    ) -> Dict[str, Any]:
        """Format SQL query."""
        # Simple formatting implementation
        # In production, use sqlparse or similar library

        # Basic formatting rules
        keywords = [
            "SELECT",
            "FROM",
            "WHERE",
            "JOIN",
            "LEFT",
            "RIGHT",
            "INNER",
            "GROUP BY",
            "ORDER BY",
            "HAVING",
            "LIMIT",
            "OFFSET",
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "ALTER",
            "DROP",
        ]

        formatted = query

        # Uppercase keywords
        for keyword in keywords:
            formatted = formatted.replace(keyword.lower(), keyword)
            formatted = formatted.replace(keyword.capitalize(), keyword)

        # Add newlines before major clauses
        for keyword in ["FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT"]:
            formatted = formatted.replace(f" {keyword}", f"\n{keyword}")

        # Indent subqueries (basic)
        lines = formatted.split("\n")
        formatted_lines = []
        indent_level = 0

        for line in lines:
            if "(" in line:
                indent_level += line.count("(")
            if ")" in line:
                indent_level -= line.count(")")

            formatted_lines.append("  " * max(0, indent_level) + line.strip())

        formatted = "\n".join(formatted_lines)

        return {
            "formatted_query": formatted,
            "dialect": dialect,
            "line_count": len(formatted_lines),
        }

    async def _analyze_query(
        self, query: str, schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze SQL query for performance issues."""
        issues = []
        suggestions = []

        query_upper = query.upper()

        # Check for SELECT *
        if "SELECT *" in query_upper:
            issues.append(
                {
                    "severity": "medium",
                    "type": "performance",
                    "message": "SELECT * can retrieve unnecessary columns",
                    "line": query_upper.find("SELECT *"),
                }
            )
            suggestions.append("Specify only the columns you need")

        # Check for missing WHERE in UPDATE/DELETE
        if (
            "UPDATE" in query_upper or "DELETE" in query_upper
        ) and "WHERE" not in query_upper:
            issues.append(
                {
                    "severity": "high",
                    "type": "safety",
                    "message": "UPDATE/DELETE without WHERE clause affects all rows",
                    "line": 0,
                }
            )
            suggestions.append("Add a WHERE clause to limit affected rows")

        # Check for LIKE with leading wildcard
        import re

        if re.search(r"LIKE\s+['\"]%", query_upper):
            issues.append(
                {
                    "severity": "medium",
                    "type": "performance",
                    "message": "Leading wildcard in LIKE prevents index usage",
                    "line": 0,
                }
            )
            suggestions.append("Consider full-text search or reverse the pattern")

        # Check for OR conditions
        if " OR " in query_upper:
            issues.append(
                {
                    "severity": "low",
                    "type": "performance",
                    "message": "OR conditions may prevent optimal index usage",
                    "line": 0,
                }
            )
            suggestions.append("Consider using UNION for better performance")

        # Check for NOT IN with subquery
        if "NOT IN" in query_upper and "(SELECT" in query_upper:
            issues.append(
                {
                    "severity": "medium",
                    "type": "performance",
                    "message": "NOT IN with subquery can be slow and has NULL issues",
                    "line": 0,
                }
            )
            suggestions.append("Consider using NOT EXISTS or LEFT JOIN")

        return {
            "query": query,
            "issues": issues,
            "suggestions": suggestions,
            "score": max(0, 100 - len(issues) * 20),  # Simple scoring
        }

    async def _validate_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database schema design."""
        issues = []
        recommendations = []

        tables = schema.get("tables", {})

        for table_name, table_info in tables.items():
            columns = table_info.get("columns", {})

            # Check for primary key
            has_primary_key = any(col.get("primary_key") for col in columns.values())
            if not has_primary_key:
                issues.append(
                    {
                        "table": table_name,
                        "type": "structure",
                        "message": "Table lacks a primary key",
                    }
                )
                recommendations.append(f"Add a primary key to {table_name}")

            # Check for appropriate data types
            for col_name, col_info in columns.items():
                data_type = col_info.get("type", "").upper()

                # Check for VARCHAR without length
                if data_type == "VARCHAR" and not col_info.get("length"):
                    issues.append(
                        {
                            "table": table_name,
                            "column": col_name,
                            "type": "data_type",
                            "message": "VARCHAR without specified length",
                        }
                    )

                # Check for TEXT when VARCHAR might be better
                if data_type == "TEXT" and col_name.endswith(("_name", "_code", "_id")):
                    recommendations.append(
                        f"Consider using VARCHAR for {table_name}.{col_name}"
                    )

            # Check indexes
            indexes = table_info.get("indexes", [])
            foreign_keys = [
                col for col, info in columns.items() if info.get("foreign_key")
            ]

            for fk in foreign_keys:
                if not any(fk in idx.get("columns", []) for idx in indexes):
                    recommendations.append(
                        f"Consider indexing foreign key {table_name}.{fk}"
                    )

        # Calculate score
        total_tables = len(tables)
        issues_count = len(issues)
        score = max(0, 100 - (issues_count * 10))

        return {
            "tables_analyzed": total_tables,
            "issues": issues,
            "recommendations": recommendations,
            "score": score,
        }

    # Prompt handlers

    async def _optimize_query_prompt(
        self, query: str, performance_metrics: Optional[Dict[Any, Any]] = None
    ) -> str:
        """Generate query optimization prompt."""
        prompt = f"""Please help me optimize this SQL query:

```sql
{query}
```
"""

        if performance_metrics:
            prompt += f"""
Current Performance Metrics:
- Execution Time: {performance_metrics.get('execution_time', 'Unknown')}
- Rows Scanned: {performance_metrics.get('rows_scanned', 'Unknown')}
- Rows Returned: {performance_metrics.get('rows_returned', 'Unknown')}
"""

        prompt += """
Please analyze the query and provide:
1. Identified performance issues
2. Optimization suggestions with explanations
3. Rewritten optimized query
4. Expected performance improvements
5. Any additional indexes that might help
"""

        return prompt

    async def _design_schema_prompt(
        self, requirements: str, constraints: Optional[Dict[Any, Any]] = None
    ) -> str:
        """Generate schema design prompt."""
        prompt = f"""Help me design a database schema for these requirements:

{requirements}
"""

        if constraints:
            prompt += "\nTechnical Constraints:\n"
            for key, value in constraints.items():
                prompt += f"- {key}: {value}\n"

        prompt += """
Please provide:
1. Complete schema design with tables and relationships
2. Explanation of design decisions
3. Normalization level and justification
4. Indexing strategy
5. Potential scalability considerations
6. Sample SQL for creating the schema
"""

        return prompt


async def main():
    """Run the database specialist server."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start server
    specialist = DatabaseSpecialist()
    await specialist.start()

    # Simple message handler for testing
    print("Database Specialist MCP Server running...")
    print(f"Authentication: {'Enabled' if specialist.auth_token else 'Disabled'}")

    # In a real implementation, this would handle stdio or network transport
    # For now, just keep the server running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down Database Specialist")


if __name__ == "__main__":
    asyncio.run(main())
