# Knowledge Management and Learning Tools Specification

This document outlines the specifications for new tools focused on knowledge management and continuous learning within OCode. These tools aim to enable the agent to acquire, organize, retrieve, and apply information from various sources, fostering self-improvement and more intelligent decision-making.

## 1. Knowledge Ingestion Tools

### 1.1. `ingest_knowledge`

**Description:** Processes and stores information from diverse sources into a structured knowledge base. This tool enables the agent to learn from documentation, code comments, web articles, and other data, making that information retrievable and applicable for future tasks.

**Parameters:**

*   **`source_type`** (string, **required**): The type of source from which to ingest knowledge.
    *   **Enum:** `file`, `directory`, `url`, `text`, `code_comments`, `api_docs`, `database_schema`.
*   **`source_path`** (string, *optional*): The path to the file or directory, or the URL to a web resource. Required for `file`, `directory`, and `url` source types.
*   **`content`** (string, *optional*): Raw text content to ingest. Required for `text` source type.
*   **`language`** (string, *optional*): The programming language of the source content (e.g., 'python', 'javascript'). Useful for `code_comments` and `api_docs`.
*   **`tags`** (array of strings, *optional*): A list of keywords or categories to associate with the ingested knowledge for easier retrieval.
*   **`metadata`** (object, *optional*): A dictionary of additional metadata to store with the knowledge entry (e.g., `{'author': 'John Doe', 'version': '1.0'}`).
*   **`recursive`** (boolean, *optional*, default: `false`): If `true` and `source_type` is `directory`, recursively ingests all supported files within the directory.
*   **`overwrite_existing`** (boolean, *optional*, default: `false`): If `true`, new knowledge with the same identifier (e.g., URL, file path) will overwrite existing entries.

**Example Usage:**

```
ingest_knowledge(
    source_type="file",
    source_path="./docs/api.md",
    tags=["api-reference", "documentation"]
)

ingest_knowledge(
    source_type="url",
    source_path="https://docs.python.org/3/library/os.html",
    tags=["python", "os-module", "standard-library"]
)

ingest_knowledge(
    source_type="text",
    content="The quick brown fox jumps over the lazy dog.",
    tags=["test", "example"]
)

ingest_knowledge(
    source_type="code_comments",
    source_path="./src/utils/helper.py",
    language="python"
)
```

**Integration Notes:**
*   Will use `file_read` and `file_list` for `file` and `directory` source types.
*   Will use `curl` or `web_fetch` for `url` source types.
*   `code_grep` can be used to extract `code_comments`.
*   `json_yaml` can be used to parse structured data from `api_docs` or `database_schema`.
*   The ingested knowledge will be stored in a persistent, searchable knowledge base (likely leveraging `memory_write` internally with a specific category, or a dedicated database).
*   Requires robust parsing capabilities for different content types (Markdown, HTML, code, etc.).

## 2. Knowledge Retrieval Tools

### 2.1. `query_knowledge_base`

**Description:** Retrieves relevant information from the structured knowledge base based on a query, keywords, or contextual information. This tool enables the agent to access previously ingested knowledge to inform its decisions and actions.

**Parameters:**

*   **`query`** (string, **required**): The natural language query or keywords to search for in the knowledge base.
*   **`filter_by_tags`** (array of strings, *optional*): A list of tags to filter the search results. Only knowledge entries associated with these tags will be returned.
*   **`filter_by_source_type`** (string, *optional*): Filters results by the original source type (e.g., `file`, `url`, `code_comments`).
*   **`max_results`** (number, *optional*, default: `5`): The maximum number of relevant knowledge entries to return.
*   **`return_full_content`** (boolean, *optional*, default: `false`): If `true`, returns the full content of the knowledge entry; otherwise, returns a snippet or summary.
*   **`context`** (string, *optional*): Additional contextual information to refine the search and improve relevance (e.g., the current task, project, or file being worked on).

**Example Usage:**

```
query_knowledge_base(
    query="how to deploy a react app to aws s3",
    filter_by_tags=["aws", "react", "deployment"]
)

query_knowledge_base(
    query="best practices for python logging",
    filter_by_source_type="code_comments",
    max_results=3
)

query_knowledge_base(
    query="explain the observer pattern",
    return_full_content=True
)
```

**Integration Notes:**
*   Will interact with the internal knowledge base (likely `memory_read` or a dedicated search index).
*   Requires advanced natural language processing (NLP) capabilities for semantic search and relevance ranking.
*   Can be used by `think` tool to gather information for analysis and decision-making.
*   Results should include metadata about the source (e.g., URL, file path, timestamp) to allow the agent to verify information.

## 3. Learning and Adaptation Tools

### 3.1. `learn_from_feedback`

**Description:** Analyzes the outcomes of previous operations (both successful and unsuccessful) and user feedback to refine internal models, strategies, and tool usage. This tool facilitates continuous self-improvement and adaptation.

**Parameters:**

*   **`feedback_type`** (string, **required**): The type of feedback being provided.
    *   **Enum:** `success`, `failure`, `user_correction`, `performance_report`, `tool_usage_log`.
*   **`operation_id`** (string, *optional*): The unique identifier of the operation or task that generated the feedback.
*   **`details`** (object, **required**): A dictionary containing the specifics of the feedback.
    *   **For `success`/`failure`:** `description` (string), `tool_used` (string), `parameters` (object), `output` (string), `error` (string, for failure), `duration` (number).
    *   **For `user_correction`:** `original_action` (object), `corrected_action` (object), `reason` (string).
    *   **For `performance_report`:** `metric_name` (string), `value` (number), `threshold` (number, optional), `context` (object).
*   **`impact_assessment`** (string, *optional*): A qualitative assessment of the feedback's impact (e.g., 'minor', 'moderate', 'significant').
*   **`recommendations`** (array of strings, *optional*): Specific suggestions for improvement derived from the feedback.

**Example Usage:**

```
learn_from_feedback(
    feedback_type="success",
    operation_id="deploy_app_123",
    details={
        "description": "Application deployed successfully to production",
        "tool_used": "deploy_application",
        "parameters": {"environment_type": "kubernetes", "app_name": "my-app"},
        "output": "Deployment completed in 30s",
        "duration": 30
    }
)

learn_from_feedback(
    feedback_type="failure",
    operation_id="refactor_code_456",
    details={
        "description": "Refactoring introduced a bug",
        "tool_used": "refactor_code",
        "parameters": {"action": "rename_symbol", "symbol": "old_func"},
        "error": "Tests failed after refactoring",
        "duration": 15
    },
    impact_assessment="significant",
    recommendations=["Improve pre-refactoring test coverage check", "Add semantic validation step"]
)

learn_from_feedback(
    feedback_type="user_correction",
    details={
        "original_action": {"tool": "file_write", "path": "/tmp/file.txt"},
        "corrected_action": {"tool": "file_write", "path": "/src/main.py"},
        "reason": "Incorrect file path provided initially"
    }
)
```

**Integration Notes:**
*   This tool will be central to the agent's self-improvement loop.
*   It will analyze structured logs and results from other tools.
*   The insights gained will be used to update internal heuristics, improve prompt generation, refine tool selection, and potentially even suggest modifications to tool definitions or implementations.
*   Requires a robust logging and telemetry system to capture operation details.
*   Can leverage `memory_write` to store learned patterns or updated strategies.

