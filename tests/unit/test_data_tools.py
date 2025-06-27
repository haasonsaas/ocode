"""Unit tests for JSON/YAML data processing tool."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from ocode_python.tools.data_tools import JsonYamlTool


class TestJsonYamlTool:
    """Test cases for JsonYamlTool."""

    @pytest.fixture
    def tool(self):
        """Create a JsonYamlTool instance."""
        return JsonYamlTool()

    @pytest.fixture
    def test_data(self):
        """Sample test data."""
        return {
            "users": [
                {"id": 1, "name": "Alice", "active": True},
                {"id": 2, "name": "Bob", "active": False},
            ],
            "config": {
                "debug": False,
                "timeout": 30,
                "features": ["auth", "api", "ui"],
            },
        }

    def test_tool_definition(self, tool):
        """Test tool definition."""
        definition = tool.definition
        assert definition.name == "json_yaml"
        assert definition.category == "Data Processing"
        assert len(definition.parameters) == 8

    @pytest.mark.asyncio
    async def test_parse_json_string(self, tool, test_data):
        """Test parsing JSON string."""
        result = await tool.execute(
            action="parse", source=json.dumps(test_data), format="json"
        )
        assert result.success
        assert "users" in result.output
        assert result.metadata["format"] == "json"

    @pytest.mark.asyncio
    async def test_parse_yaml_string(self, tool, test_data):
        """Test parsing YAML string."""
        yaml_str = yaml.dump(test_data)
        result = await tool.execute(action="parse", source=yaml_str, format="yaml")
        assert result.success
        assert "users" in result.output
        assert result.metadata["format"] == "yaml"

    @pytest.mark.asyncio
    async def test_parse_json_file(self, tool, test_data):
        """Test parsing JSON from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name

        try:
            result = await tool.execute(action="parse", source=temp_path, format="auto")
            assert result.success
            assert result.metadata["format"] == "json"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_query_simple_path(self, tool, test_data):
        """Test querying with simple JSONPath."""
        result = await tool.execute(
            action="query", source=json.dumps(test_data), query="$.config.timeout"
        )
        assert result.success
        assert json.loads(result.output) == 30
        assert result.metadata["matches"] == 1

    @pytest.mark.asyncio
    async def test_query_array_element(self, tool, test_data):
        """Test querying array elements."""
        result = await tool.execute(
            action="query", source=json.dumps(test_data), query="$.users[0].name"
        )
        assert result.success
        assert json.loads(result.output) == "Alice"

    @pytest.mark.asyncio
    async def test_query_multiple_matches(self, tool, test_data):
        """Test query with multiple matches."""
        result = await tool.execute(
            action="query", source=json.dumps(test_data), query="$.users[*].name"
        )
        assert result.success
        names = json.loads(result.output)
        assert names == ["Alice", "Bob"]
        assert result.metadata["matches"] == 2

    @pytest.mark.asyncio
    async def test_query_no_match(self, tool, test_data):
        """Test query with no matches."""
        result = await tool.execute(
            action="query", source=json.dumps(test_data), query="$.nonexistent"
        )
        assert result.success
        assert result.output == "null"
        assert result.metadata["matches"] == 0

    @pytest.mark.asyncio
    async def test_set_value(self, tool, test_data):
        """Test setting a value."""
        result = await tool.execute(
            action="set",
            source=json.dumps(test_data),
            path="$.config.debug",
            value="true",
        )
        assert result.success
        modified_data = json.loads(result.output)
        assert modified_data["config"]["debug"] is True
        assert result.metadata["updated_count"] == 1

    @pytest.mark.asyncio
    async def test_set_string_value(self, tool, test_data):
        """Test setting a string value."""
        result = await tool.execute(
            action="set",
            source=json.dumps(test_data),
            path="$.users[0].name",
            value='"Charlie"',
        )
        assert result.success
        modified_data = json.loads(result.output)
        assert modified_data["users"][0]["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_set_with_output_file(self, tool, test_data):
        """Test setting value and writing to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.json"

            result = await tool.execute(
                action="set",
                source=json.dumps(test_data),
                path="$.config.timeout",
                value="60",
                output_path=str(output_path),
            )

            assert result.success
            assert output_path.exists()

            # Verify file contents
            with open(output_path) as f:
                saved_data = json.load(f)
            assert saved_data["config"]["timeout"] == 60

    @pytest.mark.asyncio
    async def test_validate_structure(self, tool, test_data):
        """Test structure validation."""
        result = await tool.execute(action="validate", source=json.dumps(test_data))
        assert result.success
        structure = json.loads(result.output)
        assert structure["type"] == "dict"
        assert "users" in structure["keys"]
        assert result.metadata["valid"] is True

    @pytest.mark.asyncio
    async def test_invalid_action(self, tool):
        """Test invalid action."""
        result = await tool.execute(action="invalid", source="{}")
        assert not result.success
        assert "Invalid action" in result.error

    @pytest.mark.asyncio
    async def test_missing_required_params(self, tool):
        """Test missing required parameters."""
        # Missing action
        result = await tool.execute(source="{}")
        assert not result.success
        assert "Missing required parameters" in result.error

        # Missing source
        result = await tool.execute(action="parse")
        assert not result.success
        assert "Missing required parameters" in result.error

    @pytest.mark.asyncio
    async def test_invalid_json(self, tool):
        """Test parsing invalid JSON."""
        result = await tool.execute(
            action="parse", source="{'invalid': json}", format="json"
        )
        assert not result.success
        assert "Invalid JSON format" in result.error

    @pytest.mark.asyncio
    async def test_invalid_jsonpath(self, tool):
        """Test invalid JSONPath query."""
        result = await tool.execute(action="query", source="{}", query="$[invalid")
        assert not result.success
        assert "Invalid JSONPath query" in result.error
