"""
Memory and context management tools for OCode.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ResourceLock, Tool, ToolDefinition, ToolParameter, ToolResult


class MemoryReadTool(Tool):
    """Tool for reading session memory, context, and persistent data."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the memory_read tool specification.

        Returns:
            ToolDefinition with parameters for reading different types of memory
            including session, context, persistent, and filtered access options.
        """
        return ToolDefinition(
            name="memory_read",
            description="Read session memory, context data, and persistent information from various sources",  # noqa: E501  # noqa: E501
            parameters=[
                ToolParameter(
                    name="memory_type",
                    type="string",
                    description="Type of memory to read: 'session', 'context', 'persistent', 'all'",  # noqa: E501
                    required=True,
                ),
                ToolParameter(
                    name="key",
                    type="string",
                    description="Specific key to read (exact match, e.g. 'project_config', 'address'). Leave empty to read all entries.",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Category to filter by (e.g., 'variables', 'files', 'tasks', 'notes')",  # noqa: E501
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Read memory and context data."""
        try:
            # Extract parameters
            memory_type = kwargs.get("memory_type")
            key = kwargs.get("key")
            category = kwargs.get("category")
            session_id = kwargs.get("session_id")
            format = kwargs.get("format", "summary")
            max_entries = kwargs.get("max_entries", 50)

            if not memory_type:
                return ToolResult(
                    success=False, output="", error="memory_type parameter is required"
                )

            # Get memory directory
            memory_dir = self._get_memory_dir()

            result = {
                "memory_type": memory_type,
                "timestamp": datetime.now().isoformat(),
                "entries": [],
            }

            if memory_type == "session" or memory_type == "all":
                session_data = await self._read_session_memory(
                    memory_dir, session_id, key, category
                )
                result["session"] = session_data
                if memory_type != "all":
                    result["entries"] = session_data.get("entries", [])

            if memory_type == "context" or memory_type == "all":
                context_data = await self._read_context_memory(
                    memory_dir, key, category
                )
                result["context"] = context_data
                if memory_type != "all":
                    result["entries"] = context_data.get("entries", [])

            if memory_type == "persistent" or memory_type == "all":
                persistent_data = await self._read_persistent_memory(
                    memory_dir, key, category
                )
                result["persistent"] = persistent_data
                if memory_type != "all":
                    result["entries"] = persistent_data.get("entries", [])

            # Combine entries from all sources if memory_type is "all"
            if memory_type == "all":
                all_entries = []
                if "session" in result:
                    all_entries.extend(result["session"].get("entries", []))
                if "context" in result:
                    all_entries.extend(result["context"].get("entries", []))
                if "persistent" in result:
                    all_entries.extend(result["persistent"].get("entries", []))
                result["entries"] = all_entries

                # If no entries found with specific filters, try again without filters
                if not all_entries and (key or category):
                    # Retry without key/category filters to show available data
                    if "session" in result:
                        session_data = await self._read_session_memory(
                            memory_dir, session_id, None, None
                        )
                        all_entries.extend(session_data.get("entries", []))
                    if "context" in result:
                        context_data = await self._read_context_memory(
                            memory_dir, None, None
                        )
                        all_entries.extend(context_data.get("entries", []))
                    if "persistent" in result:
                        persistent_data = await self._read_persistent_memory(
                            memory_dir, None, None
                        )
                        all_entries.extend(persistent_data.get("entries", []))
                    result["entries"] = all_entries

            # Limit entries if specified
            if "entries" in result and max_entries > 0:
                result["entries"] = result["entries"][:max_entries]

            # Format output
            if format == "raw":
                output = json.dumps(result, indent=2)
            elif format == "detailed":
                output = self._format_detailed_output(result)
            else:  # summary
                output = self._format_summary_output(result)

            return ToolResult(success=True, output=output, metadata=result)

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Error reading memory: {str(e)}"
            )

    def _get_memory_dir(self) -> Path:
        """Get the memory directory path."""
        # Check if we're in a project with .ocode directory
        current_dir = Path.cwd()
        local_ocode = current_dir / ".ocode" / "memory"

        # Use local .ocode directory if it exists or if we're in a test environment
        if local_ocode.parent.exists() or "test" in str(current_dir):
            memory_dir = local_ocode
        else:
            # Otherwise use home directory for consistency across CLI and REPL
            memory_dir = Path.home() / ".ocode" / "memory"

        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir

    async def _read_session_memory(
        self,
        memory_dir: Path,
        session_id: Optional[str] = None,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read session-specific memory data."""
        session_dir = memory_dir / "sessions"
        result: Dict[str, Any] = {"entries": [], "sessions": []}

        if not session_dir.exists():
            return result

        # If specific session ID provided
        if session_id:
            session_file = session_dir / f"{session_id}.json"
            if session_file.exists():
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                result["sessions"] = [session_data]
                result["entries"] = self._filter_entries(
                    session_data.get("data", {}), key, category
                )
        else:
            # Read all sessions or find current session
            session_files = list(session_dir.glob("*.json"))
            session_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for session_file in session_files:
                try:
                    with open(session_file, "r") as f:
                        session_data = json.load(f)
                    result["sessions"].append(session_data)

                    entries = self._filter_entries(
                        session_data.get("data", {}), key, category
                    )
                    result["entries"].extend(entries)
                except Exception:
                    continue  # Skip corrupted files  # nosec B112

        return result

    async def _read_context_memory(
        self,
        memory_dir: Path,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read context memory (current working context)."""
        context_file = memory_dir / "context.json"
        result: Dict[str, Any] = {"entries": [], "context": {}}

        if context_file.exists():
            with open(context_file, "r") as f:
                context_data = json.load(f)
            result["context"] = context_data
            result["entries"] = self._filter_entries(context_data, key, category)

        return result

    async def _read_persistent_memory(
        self,
        memory_dir: Path,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Read persistent memory (long-term storage)."""
        persistent_file = memory_dir / "persistent.json"
        result: Dict[str, Any] = {"entries": [], "persistent": {}}

        if persistent_file.exists():
            with open(persistent_file, "r") as f:
                persistent_data = json.load(f)
            result["persistent"] = persistent_data
            result["entries"] = self._filter_entries(persistent_data, key, category)

        return result

    def _filter_entries(
        self,
        data: Dict[str, Any],
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter entries based on key and category."""
        entries = []

        for item_key, item_value in data.items():
            # Skip system keys
            if item_key in {"created", "updated"}:
                continue

            # Skip if specific key requested and doesn't match
            if key and item_key != key:
                continue

            # Create entry
            entry = {
                "key": item_key,
                "value": item_value,
                "type": type(item_value).__name__,
            }

            # Add category if it's in the value (for structured data)
            if isinstance(item_value, dict) and "category" in item_value:
                entry["category"] = item_value["category"]
                # Skip if category filter doesn't match
                if category and item_value["category"] != category:
                    continue
            elif category:
                # Skip if category filter specified but entry has no category
                continue

            entries.append(entry)

        return entries

    def _format_summary_output(self, result: Dict[str, Any]) -> str:
        """Format memory data as summary."""
        output = f"Memory Report ({result['memory_type'].title()})\n"
        output += f"Generated: {result['timestamp']}\n\n"

        if "session" in result:
            sessions = result["session"]["sessions"]
            output += f"Sessions: {len(sessions)} found\n"
            if sessions:
                latest = sessions[0]
                output += f"Latest: {latest.get('session_id', 'unknown')} ({latest.get('timestamp', 'unknown')})\n"  # noqa: E501

        if "context" in result:
            context_entries = len(result["context"]["entries"])
            output += f"Context entries: {context_entries}\n"

        if "persistent" in result:
            persistent_entries = len(result["persistent"]["entries"])
            output += f"Persistent entries: {persistent_entries}\n"

        entries = result.get("entries", [])
        if entries:
            output += f"\nEntries ({len(entries)}):\n"
            for entry in entries[:10]:  # Show first 10
                # For structured data, extract the actual value
                if isinstance(entry["value"], dict) and "value" in entry["value"]:
                    actual_value = entry["value"]["value"]
                    # Check if it's an appended list
                    if isinstance(actual_value, list) and all(
                        isinstance(item, dict) and "data" in item
                        for item in actual_value
                    ):
                        value_preview = f"[{len(actual_value)} entries]"
                    else:
                        value_preview = str(actual_value)
                    # Add category if available
                    if "category" in entry["value"]:
                        value_preview += f" ({entry['value']['category']})"
                else:
                    value_preview = str(entry["value"])[:80]
                    if len(str(entry["value"])) > 80:
                        value_preview += "..."
                output += f"  {entry['key']}: {value_preview}\n"

            if len(entries) > 10:
                output += f"  ... and {len(entries) - 10} more entries\n"

        return output

    def _format_detailed_output(self, result: Dict[str, Any]) -> str:
        """Format memory data with full details."""
        output = f"Detailed Memory Report ({result['memory_type'].title()})\n"
        output += f"Generated: {result['timestamp']}\n"
        output += "=" * 50 + "\n\n"

        entries = result.get("entries", [])
        for entry in entries:
            output += f"Key: {entry['key']}\n"
            output += f"Type: {entry['type']}\n"
            if "category" in entry:
                output += f"Category: {entry['category']}\n"
            output += f"Value:\n{json.dumps(entry['value'], indent=2)}\n"
            output += "-" * 30 + "\n"

        return output


class MemoryWriteTool(Tool):
    """Tool for writing and managing session memory, context, and persistent data."""

    @property
    def definition(self) -> ToolDefinition:
        """Define the memory_write tool specification.

        Returns:
            ToolDefinition with parameters for writing to different memory types
            including key-value storage, operations (set/append/delete), and categories.
        """
        return ToolDefinition(
            name="memory_write",
            description="Write and manage session memory, context data, and persistent information",  # noqa: E501
            resource_locks=[ResourceLock.MEMORY],
            parameters=[
                ToolParameter(
                    name="memory_type",
                    type="string",
                    description="Type of memory to write: 'session', 'context', 'persistent'",  # noqa: E501
                    required=True,
                ),
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Operation: 'set', 'update', 'delete', 'clear', 'append', 'lobotomize'",  # noqa: E501
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
                    description="Category for organization (e.g., 'variables', 'files', 'tasks', 'notes')",  # noqa: E501
                    required=False,
                ),
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID (auto-generated if not provided for session memory)",  # noqa: E501
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Write memory and context data."""
        try:
            # Extract parameters
            memory_type = kwargs.get("memory_type")
            operation = kwargs.get("operation")
            key = kwargs.get("key")
            value = kwargs.get("value")
            category = kwargs.get("category")
            session_id = kwargs.get("session_id")
            metadata = kwargs.get("metadata")

            if not memory_type:
                return ToolResult(
                    success=False, output="", error="memory_type parameter is required"
                )

            if not operation:
                return ToolResult(
                    success=False, output="", error="operation parameter is required"
                )

            # Get memory directory
            memory_dir = self._get_memory_dir()
            memory_dir.mkdir(parents=True, exist_ok=True)

            result_message = ""

            if memory_type == "session":
                result_message = await self._write_session_memory(
                    memory_dir, operation, key, value, category, session_id, metadata
                )
            elif memory_type == "context":
                result_message = await self._write_context_memory(
                    memory_dir, operation, key, value, category, metadata
                )
            elif memory_type == "persistent":
                result_message = await self._write_persistent_memory(
                    memory_dir, operation, key, value, category, metadata
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown memory type: {memory_type}",
                )

            return ToolResult(
                success=True,
                output=result_message,
                metadata={
                    "memory_type": memory_type,
                    "operation": operation,
                    "key": key,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Error writing memory: {str(e)}"
            )

    def _get_memory_dir(self) -> Path:
        """Get the memory directory path."""
        # Check if we're in a project with .ocode directory
        current_dir = Path.cwd()
        local_ocode = current_dir / ".ocode" / "memory"

        # Use local .ocode directory if it exists or if we're in a test environment
        if local_ocode.parent.exists() or "test" in str(current_dir):
            memory_dir = local_ocode
        else:
            # Otherwise use home directory for consistency across CLI and REPL
            memory_dir = Path.home() / ".ocode" / "memory"

        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir

    async def _write_session_memory(
        self,
        memory_dir: Path,
        operation: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write session-specific memory data."""
        session_dir = memory_dir / "sessions"
        session_dir.mkdir(exist_ok=True)

        # Generate session ID if not provided
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        session_file = session_dir / f"{session_id}.json"

        # Load existing session data or create new
        if session_file.exists():
            with open(session_file, "r") as f:
                session_data = json.load(f)
        else:
            session_data = {
                "session_id": session_id,
                "created": datetime.now().isoformat(),
                "data": {},
            }

        session_data["updated"] = datetime.now().isoformat()

        result = self._perform_operation(
            session_data["data"], operation, key, value, category, metadata
        )

        # Save session data
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=2)

        return result

    async def _write_context_memory(
        self,
        memory_dir: Path,
        operation: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write context memory (current working context)."""
        context_file = memory_dir / "context.json"

        # Load existing context data or create new
        if context_file.exists():
            with open(context_file, "r") as f:
                context_data = json.load(f)
        else:
            context_data = {"created": datetime.now().isoformat()}

        context_data["updated"] = datetime.now().isoformat()

        result = self._perform_operation(
            context_data, operation, key, value, category, metadata
        )

        # Save context data
        with open(context_file, "w") as f:
            json.dump(context_data, f, indent=2)

        return result

    async def _write_persistent_memory(
        self,
        memory_dir: Path,
        operation: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write persistent memory (long-term storage)."""
        persistent_file = memory_dir / "persistent.json"

        # Load existing persistent data or create new
        if persistent_file.exists():
            with open(persistent_file, "r") as f:
                persistent_data = json.load(f)
        else:
            persistent_data = {"created": datetime.now().isoformat()}

        persistent_data["updated"] = datetime.now().isoformat()

        result = self._perform_operation(
            persistent_data, operation, key, value, category, metadata
        )

        # Save persistent data
        with open(persistent_file, "w") as f:
            json.dump(persistent_data, f, indent=2)

        return result

    def _perform_operation(
        self,
        data: Dict[str, Any],
        operation: str,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Perform the specified operation on the data."""

        if operation == "set":
            if key is None:
                raise ValueError("Key is required for 'set' operation")

            # Validate that value is not None or empty for meaningful storage
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise ValueError(f"Cannot store empty/null value for key '{key}'")

            # Structure the value with metadata
            structured_value = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }  # noqa: E501

            if category:
                structured_value["category"] = category

            if metadata:
                structured_value["metadata"] = metadata

            data[key] = structured_value
            return f"Set key '{key}' with value '{value}'"

        elif operation == "update":
            if key is None:
                raise ValueError("Key is required for 'update' operation")

            if key not in data:
                return f"Key '{key}' not found for update"

            # Update existing entry
            if isinstance(data[key], dict) and "value" in data[key]:
                if value is not None:
                    data[key]["value"] = value
                data[key]["timestamp"] = datetime.now().isoformat()

                if category:
                    data[key]["category"] = category

                if metadata:
                    data[key].setdefault("metadata", {}).update(metadata)
            else:
                # Legacy format, convert to structured
                data[key] = {
                    "value": value if value is not None else data[key],
                    "timestamp": datetime.now().isoformat(),
                }

                if category:
                    data[key]["category"] = category

                if metadata:
                    data[key]["metadata"] = metadata

            return f"Updated key '{key}' with value '{value if value is not None else data[key]['value']}'"  # noqa: E501

        elif operation == "delete":
            if key is None:
                raise ValueError("Key is required for 'delete' operation")

            if key in data:
                del data[key]
                return f"Deleted key '{key}'"
            else:
                return f"Key '{key}' not found for deletion"

        elif operation == "clear":
            if key:
                # Clear specific key
                if key in data:
                    data[key] = {}
                    return f"Cleared key '{key}'"
                else:
                    return f"Key '{key}' not found for clearing"
            else:
                # Clear all data (except system keys)
                system_keys = {"created", "updated"}
                keys_to_delete = [k for k in data.keys() if k not in system_keys]
                for k in keys_to_delete:
                    del data[k]
                return f"Cleared all data ({len(keys_to_delete)} entries)"

        elif operation == "lobotomize":
            # Complete memory wipe - clear everything including timestamps
            system_keys = {"created", "updated"}
            keys_to_delete = [k for k in data.keys() if k not in system_keys]
            deleted_count = len(keys_to_delete)

            for k in keys_to_delete:
                del data[k]

            # Reset timestamps
            data["updated"] = datetime.now().isoformat()

            return f"🧠💥 Memory lobotomized! Cleared {deleted_count} entries. Starting fresh..."  # noqa: E501

        elif operation == "append":
            if key is None:
                raise ValueError("Key is required for 'append' operation")

            if key not in data:
                data[key] = {"value": [], "timestamp": datetime.now().isoformat()}

                if category:
                    data[key]["category"] = category

            # Ensure the value is a list for appending
            current_value = (
                data[key].get("value", [])
                if isinstance(data[key], dict)
                else data[key]  # noqa: E501
            )
            if not isinstance(current_value, list):
                current_value = [current_value]

            current_value.append(
                {
                    "data": value,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata,
                }
            )

            if isinstance(data[key], dict):
                data[key]["value"] = current_value
                data[key]["timestamp"] = datetime.now().isoformat()
            else:
                data[key] = {
                    "value": current_value,
                    "timestamp": datetime.now().isoformat(),
                }

                if category:
                    data[key]["category"] = category

            return f"Appended to key '{key}' (now {len(current_value)} entries)"

        else:
            raise ValueError(f"Unknown operation: {operation}")
