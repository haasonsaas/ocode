"""Unit tests for EnvironmentTool."""

import os
import tempfile
from unittest.mock import patch

import pytest

from ocode_python.tools.env_tool import EnvironmentTool


class TestEnvironmentTool:
    """Test EnvironmentTool functionality."""

    @pytest.fixture
    def tool(self):
        """Create EnvironmentTool instance."""
        return EnvironmentTool()

    @pytest.fixture
    def temp_env_file(self):
        """Create a temporary .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("TEST_VAR=test_value\n")
            f.write("ANOTHER_VAR=another_value\n")
            f.write('QUOTED_VAR="quoted value"\n')
            f.write("# This is a comment\n")
            f.write("EMPTY_VAR=\n")
            temp_path = f.name

        yield temp_path

        # Cleanup
        try:
            os.unlink(temp_path)
        except Exception:
            pass

    def test_tool_definition(self, tool):
        """Test tool definition."""
        assert tool.definition.name == "env"
        assert tool.definition.category == "System Operations"
        assert len(tool.definition.parameters) == 7

    @pytest.mark.asyncio
    async def test_get_action(self, tool):
        """Test get action."""
        with patch.dict(os.environ, {"TEST_ENV_VAR": "test_value"}):
            result = await tool.execute(action="get", name="TEST_ENV_VAR")
            assert result.success
            # The env tool outputs just the value for text format
            assert result.output == "test_value"

    @pytest.mark.asyncio
    async def test_get_action_not_found(self, tool):
        """Test get action with non-existent variable."""
        with patch.dict(os.environ, {}, clear=True):
            result = await tool.execute(action="get", name="NON_EXISTENT_VAR")
            assert result.success
            assert "Environment variable 'NON_EXISTENT_VAR' is not set" in result.output

    @pytest.mark.asyncio
    async def test_set_action(self, tool):
        """Test set action."""
        with patch.dict(os.environ, {}, clear=True):
            result = await tool.execute(action="set", name="NEW_VAR", value="new_value")

            assert result.success
            assert "Set NEW_VAR=new_value" in result.output
            assert os.environ.get("NEW_VAR") == "new_value"

    @pytest.mark.asyncio
    async def test_set_action_update_existing(self, tool):
        """Test set action updating existing variable."""
        with patch.dict(os.environ, {"EXISTING_VAR": "old_value"}, clear=True):
            result = await tool.execute(
                action="set", name="EXISTING_VAR", value="new_value"
            )

            assert result.success
            assert "Set EXISTING_VAR=new_value" in result.output
            assert os.environ.get("EXISTING_VAR") == "new_value"

    @pytest.mark.asyncio
    async def test_unset_action(self, tool):
        """Test unset action."""
        with patch.dict(os.environ, {"TO_DELETE": "value"}, clear=True):
            result = await tool.execute(action="unset", name="TO_DELETE")

            assert result.success
            assert "Unset TO_DELETE" in result.output
            assert "TO_DELETE" not in os.environ

    @pytest.mark.asyncio
    async def test_unset_action_not_found(self, tool):
        """Test unset action with non-existent variable."""
        with patch.dict(os.environ, {}, clear=True):
            result = await tool.execute(action="unset", name="NON_EXISTENT")

            assert result.success
            assert "Environment variable 'NON_EXISTENT' was not set" in result.output

    @pytest.mark.asyncio
    async def test_list_action(self, tool):
        """Test list action."""
        test_env = {"VAR1": "value1", "VAR2": "value2", "TEST_VAR": "test_value"}

        with patch.dict(os.environ, test_env, clear=True):
            result = await tool.execute(action="list")

            assert result.success
            assert "VAR1=value1" in result.output
            assert "VAR2=value2" in result.output
            assert "TEST_VAR=test_value" in result.output
            assert result.metadata["count"] == 3

    @pytest.mark.asyncio
    async def test_list_action_with_pattern(self, tool):
        """Test list action with pattern filtering."""
        test_env = {
            "TEST_VAR1": "value1",
            "TEST_VAR2": "value2",
            "OTHER_VAR": "other_value",
            "ANOTHER_TEST": "test_value",
        }

        with patch.dict(os.environ, test_env, clear=True):
            result = await tool.execute(action="list", pattern="TEST")

            assert result.success
            assert "TEST_VAR1=value1" in result.output
            assert "TEST_VAR2=value2" in result.output
            assert "ANOTHER_TEST=test_value" in result.output
            assert "OTHER_VAR" not in result.output
            assert result.metadata["count"] == 3

    @pytest.mark.asyncio
    async def test_list_action_empty(self, tool):
        """Test list action with no environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            result = await tool.execute(action="list")

            assert result.success
            assert "No environment variables found" in result.output

    @pytest.mark.asyncio
    async def test_load_action(self, tool, temp_env_file):
        """Test load action."""
        with patch.dict(os.environ, {}, clear=True):
            # Load with export=True to actually set the variables
            result = await tool.execute(action="load", file=temp_env_file, export=True)

            assert result.success
            assert f"Loaded 4 variables from {temp_env_file}:" in result.output
            assert "TEST_VAR=test_value" in result.output
            assert "ANOTHER_VAR=another_value" in result.output
            assert "QUOTED_VAR=quoted value" in result.output

            # Verify variables were actually set (only works with export=True)
            assert os.environ.get("TEST_VAR") == "test_value"
            assert os.environ.get("ANOTHER_VAR") == "another_value"
            assert os.environ.get("QUOTED_VAR") == "quoted value"

    @pytest.mark.asyncio
    async def test_load_action_file_not_found(self, tool):
        """Test load action with non-existent file."""
        result = await tool.execute(action="load", file="/non/existent/file.env")

        assert not result.success
        assert "File not found: /non/existent/file.env" in result.error

    @pytest.mark.asyncio
    async def test_load_action_with_updates(self, tool, temp_env_file):
        """Test load action updating existing variables."""
        with patch.dict(os.environ, {"TEST_VAR": "old_value"}, clear=True):
            # Load with export=True to actually update the variables
            result = await tool.execute(action="load", file=temp_env_file, export=True)

            assert result.success
            assert f"Loaded 4 variables from {temp_env_file}:" in result.output
            assert "TEST_VAR=test_value" in result.output
            # Verify it was updated
            assert os.environ.get("TEST_VAR") == "test_value"

    @pytest.mark.asyncio
    async def test_save_action(self, tool):
        """Test save action."""
        test_env = {"SAVE_VAR1": "value1", "SAVE_VAR2": "value2", "OTHER_VAR": "other"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            temp_path = f.name

        try:
            with patch.dict(os.environ, test_env, clear=True):
                result = await tool.execute(
                    action="save", file=temp_path, pattern="SAVE"
                )

                assert result.success
                assert "Saved 2" in result.output and temp_path in result.output

                # Verify file contents
                with open(temp_path, "r") as f:
                    content = f.read()
                    assert "SAVE_VAR1=value1" in content
                    assert "SAVE_VAR2=value2" in content
                    assert "OTHER_VAR" not in content
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_save_action_all_vars(self, tool):
        """Test save action with all variables."""
        test_env = {"VAR1": "value1", "VAR2": "value2"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            temp_path = f.name

        try:
            with patch.dict(os.environ, test_env, clear=True):
                result = await tool.execute(action="save", file=temp_path)

                assert result.success
                assert "Saved 2" in result.output and temp_path in result.output
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_save_action_with_special_chars(self, tool):
        """Test save action with special characters in values."""
        test_env = {
            "VAR_WITH_SPACES": "value with spaces",
            "VAR_WITH_QUOTES": 'value with "quotes"',
            "VAR_WITH_EQUALS": "key=value",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            temp_path = f.name

        try:
            with patch.dict(os.environ, test_env, clear=True):
                result = await tool.execute(action="save", file=temp_path)

                assert result.success
                # Verify file contents
                with open(temp_path, "r") as f:
                    content = f.read()
                    assert 'VAR_WITH_SPACES="value with spaces"' in content
                    assert 'VAR_WITH_QUOTES="value with \\"quotes\\""' in content
                    # The tool might not quote values with equals signs based on implementation  # noqa: E501
                    assert (
                        "VAR_WITH_EQUALS=key=value" in content
                        or 'VAR_WITH_EQUALS="key=value"' in content
                    )
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_invalid_action(self, tool):
        """Test invalid action."""
        result = await tool.execute(action="invalid")

        assert not result.success
        assert (
            "Invalid action" in result.error
            and "get, set, unset, list, load, save" in result.error
        )

    @pytest.mark.asyncio
    async def test_missing_name_for_get(self, tool):
        """Test get action without name."""
        result = await tool.execute(action="get")

        assert not result.success
        assert "Name parameter is required for 'get' action" in result.error

    @pytest.mark.asyncio
    async def test_missing_name_for_set(self, tool):
        """Test set action without name."""
        result = await tool.execute(action="set", value="test")

        assert not result.success
        assert "Name parameter is required for 'set' action" in result.error

    @pytest.mark.asyncio
    async def test_missing_value_for_set(self, tool):
        """Test set action without value."""
        result = await tool.execute(action="set", name="TEST")

        assert not result.success
        assert "Value parameter is required for 'set' action" in result.error

    @pytest.mark.asyncio
    async def test_load_action_with_default_file(self, tool):
        """Test load action uses default .env file."""
        # This test shows that load without file parameter uses '.env' as default
        # So it doesn't fail, it tries to load .env
        result = await tool.execute(action="load")

        # It succeeds if .env exists, or fails if it doesn't
        # In test environment, .env might exist
        assert result.success or "File not found: .env" in str(result.error)

    @pytest.mark.asyncio
    async def test_save_action_with_default_file(self, tool):
        """Test save action uses default .env file."""
        # Save without file parameter uses '.env' as default
        with patch.dict(os.environ, {"TEST_SAVE": "value"}, clear=True):
            result = await tool.execute(action="save")

            # It should succeed and save to .env
            assert result.success
            assert "Saved 1" in result.output
            assert ".env" in result.output

    @pytest.mark.asyncio
    async def test_invalid_env_name(self, tool):
        """Test setting variable with invalid name."""
        result = await tool.execute(action="set", name="123INVALID", value="test")

        assert not result.success
        assert "Invalid variable name" in result.error

    @pytest.mark.asyncio
    async def test_load_with_syntax_error(self, tool):
        """Test load action with malformed .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("VALID_VAR=valid\n")
            f.write("INVALID LINE WITHOUT EQUALS\n")
            f.write("ANOTHER_VALID=value\n")
            temp_path = f.name

        try:
            with patch.dict(os.environ, {}, clear=True):
                # Should still load valid lines (with export=True to set them)
                result = await tool.execute(action="load", file=temp_path, export=True)

                assert result.success
                assert "Loaded 2 variables from" in result.output
                assert os.environ.get("VALID_VAR") == "valid"
                assert os.environ.get("ANOTHER_VALID") == "value"
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
