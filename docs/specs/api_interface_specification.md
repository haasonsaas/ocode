# Comprehensive API and Interface Specification for ocode Agent Architecture

## 1. Introduction

This document specifies the Application Programming Interfaces (APIs) and communication protocols governing the interactions between the various components of the ocode agent architecture. As the ocode agent evolves into a sophisticated, self-improving system, clear, robust, and well-defined interfaces are paramount for ensuring modularity, scalability, maintainability, and seamless interoperability between its core pillars: the Explicit Task Planning (ETP) system, the Code Knowledge Graph (CKG), and the Self-Improvement (SI) system (including its sub-components: Performance Monitoring & Analytics (PMA), Feedback & Learning Loop (FLL), Tool Generation & Augmentation (TGA), and Knowledge Base Integration (KBI)).

The goal of this specification is to provide a definitive contract for component developers, enabling independent development and deployment while guaranteeing system-wide coherence and data integrity. It will cover communication patterns, data models, service endpoints, authentication, error handling, and versioning strategies.

## 2. Core Principles of API Design

Our API design will adhere to the following principles to ensure a robust and future-proof architecture:

*   **Modularity & Decoupling:** Components should interact primarily through well-defined APIs, minimizing direct dependencies and allowing for independent evolution and deployment.
*   **Clarity & Consistency:** APIs will follow consistent naming conventions, data structures, and interaction patterns to reduce cognitive load for developers and improve system predictability.
*   **Scalability:** The chosen protocols and design patterns will support high throughput and low latency, accommodating the increasing data volume and computational demands of a continuously learning agent.
*   **Resilience & Error Handling:** APIs will be designed to gracefully handle errors, provide informative feedback, and support retry mechanisms where appropriate.
*   **Security:** All inter-component communication will be secured to protect sensitive data and prevent unauthorized access or manipulation.
*   **Observability:** APIs will expose metrics and logging capabilities to facilitate monitoring, debugging, and performance analysis.
*   **Versioning:** A clear strategy for API versioning will be established to manage changes and ensure backward compatibility, minimizing disruption to integrated components.
*   **Data Integrity:** Data models will enforce strict schemas and validation rules to maintain the consistency and quality of information exchanged across the system.

## 3. Inter-Component Communication Protocols

The ocode agent architecture will employ a hybrid approach to inter-component communication, leveraging different protocols based on the specific interaction patterns and performance requirements.

### 3.1. Synchronous Request/Response (gRPC)

For real-time, high-performance, and strongly-typed communication between core services (e.g., ETP querying CKG for knowledge, TGA requesting code generation from an LLM service), gRPC will be the primary protocol. gRPC offers:

*   **Performance:** Built on HTTP/2, it supports multiplexing, header compression, and server push, leading to lower latency and higher throughput.
*   **Strong Typing:** Uses Protocol Buffers for defining service interfaces and message structures, ensuring strict data contracts and compile-time validation.

*   **Bidirectional Streaming:** Supports streaming RPCs, useful for continuous data flows (e.g., real-time feedback from execution environments).

**Use Cases:**
*   ETP querying CKG for `CodeEntity` or `ProblemType` information.
*   FLL (AEA/SPI) querying CKG for contextual data during analysis.
*   TGA requesting code synthesis from an internal LLM service.
*   Tool Dispatcher invoking internal, generated tools.

### 3.2. Asynchronous Event Streaming (Kafka/Pub-Sub)

For decoupled, scalable, and fault-tolerant communication, especially for telemetry, logging, and notifications, an asynchronous event streaming platform (e.g., Apache Kafka, Google Cloud Pub/Sub) will be utilized. This enables components to publish events without direct knowledge of their consumers, and consumers to process events independently.

*   **Decoupling:** Producers and consumers are independent, improving system resilience and allowing for easier evolution of individual components.
*   **Scalability:** Designed for high-throughput, low-latency data ingestion and distribution.

*   **Durability:** Events are persisted, allowing consumers to catch up on missed events or for historical analysis.
*   **Real-time Processing:** Supports real-time stream processing for immediate reactions to events.

**Use Cases:**
*   PMA publishing `ExecutionAttempt` logs, `Error` events, and `resource_metrics`.
*   FLL publishing `FailureAnalysisReport` and `ProvenStrategy` objects.
*   TGA publishing `ProposedTool` validation results.
*   KBI publishing `PlanModificationProposal` and `ToolReviewRequest` events for HITL.
*   General system-wide logging and audit trails.

### 3.3. RESTful HTTP (for External/Human-facing Interfaces)

For external integrations, human-facing dashboards, and less performance-critical internal interactions, RESTful HTTP APIs will be used. REST offers:

*   **Simplicity & Ubiquity:** Widely understood and supported, making integration with external systems and UIs straightforward.
*   **Statelessness:** Simplifies server design and improves scalability.

*   **Resource-Oriented:** Intuitive for managing resources (e.g., `Task` objects, `User` profiles).

**Use Cases:**
*   User interface (UI) interacting with the agent to submit `Task` requests or review `HITL` queues.
*   External systems submitting `Task` requests or querying agent status.
*   Internal administrative interfaces.

### 3.4. Shared Memory / In-Process (for tightly coupled modules)

For very tightly coupled modules within the same process space (e.g., a sub-component directly calling a utility function within the same service), direct function calls or shared memory mechanisms may be used for maximum performance. These interactions are typically not exposed as formal APIs.

**Use Cases:**
*   Internal utility functions within the ETP or FLL services.
*   Direct access to in-memory caches or data structures.

**Note:** The choice of protocol for each interaction will be explicitly defined in the subsequent sections detailing component-specific APIs. All network communication will be encrypted (e.g., TLS for gRPC and HTTPS for REST).

## 4. Data Models for API Payloads

This section defines the canonical data models for the primary entities exchanged between ocode agent components. These models will be specified using Protocol Buffers (Protobuf) for gRPC-based communication, and their JSON equivalents for RESTful interfaces and event streaming. UUIDs will be used for all primary identifiers to ensure global uniqueness.

### 4.1. `Task` Data Model

Represents a high-level objective or user request submitted to the ocode agent.

```protobuf
message Task {
  string task_id = 1; // Unique identifier for the task (UUID)
  string user_id = 2; // Identifier of the user who initiated the task
  string prompt = 3; // Natural language description of the task
  repeated string context_files = 4; // List of absolute file paths relevant to the task
  map<string, string> metadata = 5; // Arbitrary key-value pairs for additional context
  TaskStatus status = 6; // Current status of the task
  google.protobuf.Timestamp created_at = 7; // Timestamp of task creation
  google.protobuf.Timestamp updated_at = 8; // Last updated timestamp
  google.protobuf.Timestamp completed_at = 9; // Timestamp of task completion (if applicable)
  string assigned_agent_id = 10; // ID of the agent instance currently handling the task
}

enum TaskStatus {
  TASK_STATUS_UNSPECIFIED = 0;
  TASK_STATUS_PENDING = 1;
  TASK_STATUS_IN_PROGRESS = 2;
  TASK_STATUS_COMPLETED_SUCCESS = 3;
  TASK_STATUS_COMPLETED_FAILURE = 4;
  TASK_STATUS_CANCELLED = 5;
  TASK_STATUS_PAUSED = 6;
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "user_id": "user-123",
  "prompt": "Refactor the authentication module to use OAuth2",
  "context_files": [
    "/project/src/auth.py",
    "/project/tests/test_auth.py"
  ],
  "metadata": {
    "priority": "high",
    "jira_ticket": "OCD-456"
  },
  "status": "TASK_STATUS_IN_PROGRESS",
  "created_at": "2025-06-26T10:00:00Z",
  "updated_at": "2025-06-26T10:30:00Z",
  "assigned_agent_id": "agent-alpha-1"
}
```

### 4.2. `ExecutionAttempt` Data Model

Represents a single attempt by the agent to execute a tool or a sequence of internal actions as part of a `Task`. This is a key data point for the Performance Monitoring & Analytics (PMA) component.

```protobuf
message ExecutionAttempt {
  string attempt_id = 1; // Unique identifier for the execution attempt (UUID)
  string task_id = 2; // ID of the parent task
  string agent_id = 3; // ID of the agent instance performing the attempt
  string tool_name = 4; // Name of the tool invoked (e.g., "run_shell_command", "read_file")
  google.protobuf.Struct input_parameters = 5; // JSON representation of input parameters to the tool
  string raw_command = 6; // For shell tools, the raw command string executed
  google.protobuf.Timestamp started_at = 7; // Timestamp when the attempt started
  google.protobuf.Timestamp completed_at = 8; // Timestamp when the attempt completed
  ExecutionOutcome outcome = 9; // Outcome of the attempt
  string stdout = 10; // Standard output from the tool execution
  string stderr = 11; // Standard error from the tool execution
  int32 exit_code = 12; // Exit code of the tool execution
  string error_message = 13; // High-level error message if outcome is FAILURE
  google.protobuf.Struct resource_metrics = 14; // Resource usage metrics (CPU, memory, tokens, API calls)
  string environment_snapshot_id = 15; // Reference to an Environment snapshot (UUID)
}

enum ExecutionOutcome {
  EXECUTION_OUTCOME_UNSPECIFIED = 0;
  EXECUTION_OUTCOME_SUCCESS = 1;
  EXECUTION_OUTCOME_FAILURE = 2;
  EXECUTION_OUTCOME_TIMEOUT = 3;
  EXECUTION_OUTCOME_INTERRUPTED = 4;
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "attempt_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "agent_id": "agent-alpha-1",
  "tool_name": "run_shell_command",
  "input_parameters": {
    "command": "git status"
  },
  "raw_command": "git status",
  "started_at": "2025-06-26T10:30:00Z",
  "completed_at": "2025-06-26T10:30:01Z",
  "outcome": "EXECUTION_OUTCOME_SUCCESS",
  "stdout": "On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean\n",
  "stderr": "",
  "exit_code": 0,
  "error_message": "",
  "resource_metrics": {
    "cpu_usage_percent": 0.5,
    "memory_usage_mb": 10.2,
    "token_count_in": 5,
    "token_count_out": 50
  },
  "environment_snapshot_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef01"
}
```

### 4.3. `Error` Data Model

Represents a specific, observed error event resulting from a failed `ExecutionAttempt`. This data is crucial for the Automated Error Analysis (AEA) component of the FLL.

```protobuf
message Error {
  string error_id = 1; // Unique identifier for the error instance (UUID)
  string attempt_id = 2; // ID of the ExecutionAttempt that resulted in this error
  string error_code = 3; // Standardized error code (e.g., HTTP status, OS error code, custom code)
  string error_message = 4; // Raw error message from stdout/stderr
  string stack_trace = 5; // Full stack trace if available
  bool is_transient = 6; // True if the error is likely temporary (e.g., network glitch, rate limit)
  google.protobuf.Timestamp occurred_at = 7; // Timestamp when the error was observed
  google.protobuf.Struct context = 8; // Additional context relevant to the error (e.g., file path, line number)
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "error_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef02",
  "attempt_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
  "error_code": "128",
  "error_message": "*** Please tell me who you are.\n\nRun\n\n  git config --global user.email \"you@example.com\"\n  git config --global user.name \"Your Name\"\n\nto set your account's default identity.\nOmit --global to set the identity only in this repository.",
  "stack_trace": "",
  "is_transient": false,
  "occurred_at": "2025-06-26T10:30:01Z",
  "context": {
    "tool": "git",
    "subcommand": "commit"
  }
}
```

### 4.4. `ErrorPattern` Data Model

Represents a generalized, canonical class of errors. This is a key entity in the Self-Improvement Knowledge Graph, used by AEA for classification and by APR for strategy lookup.

```protobuf
message ErrorPattern {
  string pattern_id = 1; // Unique identifier for the error pattern (UUID)
  string name = 2; // Human-readable name (e.g., "GitAuthenticationFailure", "PythonModuleNotFound")
  string description = 3; // Detailed description of the error pattern
  repeated string canonical_regex = 4; // List of regex patterns to match against error messages/stderr
  repeated string common_causes = 5; // List of common underlying causes for this pattern
  repeated string suggested_remediations = 6; // High-level suggested fixes
  google.protobuf.Timestamp created_at = 7;
  google.protobuf.Timestamp updated_at = 8;
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "pattern_id": "d4e5f6a7-b8c9-0123-4567-890abcdef03",
  "name": "GitAuthenticationFailure",
  "description": "Occurs when Git operations fail due to missing or incorrect user identity configuration.",
  "canonical_regex": [
    ".*Please tell me who you are.*",
    ".*Authentication failed for.*"
  ],
  "common_causes": [
    "user.email or user.name not configured",
    "SSH key not added to agent",
    "Incorrect personal access token"
  ],
  "suggested_remediations": [
    "Configure git user.email and user.name",
    "Add SSH key to ssh-agent",
    "Generate new personal access token"
  ],
  "created_at": "2025-06-01T00:00:00Z",
  "updated_at": "2025-06-15T12:00:00Z"
}
```

### 4.5. `FailureAnalysisReport` Data Model

Represents a structured report generated by the Automated Error Analysis (AEA) component, detailing the diagnosis of a failed `ExecutionAttempt`.

```protobuf
message FailureAnalysisReport {
  string report_id = 1; // Unique identifier for the report (UUID)
  string task_id = 2; // ID of the parent task
  string failed_attempt_id = 3; // ID of the ExecutionAttempt that failed
  string error_id = 4; // ID of the specific Error instance
  string error_pattern_id = 5; // ID of the matched ErrorPattern (if any)
  string inferred_root_cause = 6; // Inferred root cause of the failure
  string culprit_action_id = 7; // ID of the specific action/tool call identified as the culprit
  string proposed_remediation_strategy_description = 8; // High-level description of proposed fix
  float confidence_score = 9; // Confidence in the analysis (0.0-1.0)
  google.protobuf.Timestamp analysis_timestamp = 10; // Timestamp of the analysis
  repeated string relevant_ckg_entities = 11; // List of CKG entity IDs relevant to the analysis
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "report_id": "e5f6a7b8-c9d0-1234-5678-90abcdef04",
  "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "failed_attempt_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
  "error_id": "c3d4e5f6-a7b8-9012-3456-7890abcdef02",
  "error_pattern_id": "d4e5f6a7-b8c9-0123-4567-890abcdef03",
  "inferred_root_cause": "Git user identity not configured globally.",
  "culprit_action_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
  "proposed_remediation_strategy_description": "Configure git global user.email and user.name before committing.",
  "confidence_score": 0.95,
  "analysis_timestamp": "2025-06-26T10:30:05Z",
  "relevant_ckg_entities": [
    "ckg-entity-git-config",
    "ckg-entity-user-identity"
  ]
}
```

### 4.6. `ProvenStrategy` Data Model

Represents a generalized, empirically validated sequence of actions or plan fragment that has consistently led to successful outcomes for a specific problem type. Generated by the Success Pattern Identification (SPI) component.

```protobuf
message ProvenStrategy {
  string strategy_id = 1; // Unique identifier for the proven strategy (UUID)
  string name = 2; // Human-readable name for the strategy
  string description = 3; // Detailed description of what the strategy achieves
  google.protobuf.Struct template_plan_fragment = 4; // Parameterized representation of the action sequence
  google.protobuf.Struct applicability_conditions = 5; // Rules/conditions for when this strategy is applicable
  google.protobuf.Struct average_performance_metrics = 6; // Avg. duration, token usage, etc.
  float success_rate = 7; // Historical success rate (0.0-1.0)
  google.protobuf.Timestamp created_at = 8;
  google.protobuf.Timestamp updated_at = 9;
  repeated string related_problem_types = 10; // List of ProblemType IDs this strategy addresses
}
```

**JSON Example (for REST/Kafka):**

```json
{
  "strategy_id": "f6a7b8c9-d0e1-2345-6789-0abcdef05",
  "name": "GitGlobalConfigSetup",
  "description": "Sets up global Git user.email and user.name for authentication.",
  "template_plan_fragment": {
    "steps": [
      {
        "tool": "run_shell_command",
        "parameters": {
          "command": "git config --global user.email \"${user_email}\"
