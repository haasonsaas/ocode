"""
Tests for the safe parser utility.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from ocode_python.utils.safe_parser import (
    FileSizeError,
    ParseError,
    DEFAULT_JSON_MAX_SIZE,
    DEFAULT_YAML_MAX_SIZE,
    get_file_size,
    validate_file_size,
    safe_json_load,
    safe_json_loads,
    safe_yaml_load,
    safe_yaml_loads,
    stream_json_objects,
    stream_yaml_documents,
    safe_json_dump,
    safe_yaml_dump,
    load_json,
    load_yaml,
    parse_json,
    parse_yaml,
    YAML_AVAILABLE,
)


class TestFileSizeValidation:
    """Test file size validation functionality."""

    def test_get_file_size_existing_file(self):
        """Test getting size of an existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            size = get_file_size(temp_path)
            assert size == len("test content")
        finally:
            os.unlink(temp_path)

    def test_get_file_size_nonexistent_file(self):
        """Test getting size of a nonexistent file."""
        with pytest.raises(ParseError, match="Unable to get file size"):
            get_file_size("/nonexistent/file.json")

    def test_validate_file_size_success(self):
        """Test successful file size validation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("small content")
            temp_path = f.name
        
        try:
            # Should not raise an exception
            validate_file_size(temp_path, 1000, "JSON")
        finally:
            os.unlink(temp_path)

    def test_validate_file_size_exceeds_limit(self):
        """Test file size validation when file exceeds limit."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("large content that exceeds limit")
            temp_path = f.name
        
        try:
            with pytest.raises(FileSizeError) as exc_info:
                validate_file_size(temp_path, 10, "JSON")  # Very small limit
            
            assert "exceeds the maximum allowed size" in str(exc_info.value)
            assert exc_info.value.file_size > 10
            assert exc_info.value.max_size == 10
        finally:
            os.unlink(temp_path)


class TestSafeJSONParsing:
    """Test safe JSON parsing functionality."""

    def test_safe_json_load_valid_file(self):
        """Test loading valid JSON from file."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name
        
        try:
            result = safe_json_load(temp_path)
            assert result == test_data
        finally:
            os.unlink(temp_path)

    def test_safe_json_load_invalid_json(self):
        """Test loading invalid JSON from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with pytest.raises(ParseError, match="Invalid JSON"):
                safe_json_load(temp_path)
        finally:
            os.unlink(temp_path)

    def test_safe_json_load_file_too_large(self):
        """Test loading JSON file that exceeds size limit."""
        large_data = {"key": "x" * 1000}  # Create reasonably sized data
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(large_data, f)
            temp_path = f.name
        
        try:
            with pytest.raises(FileSizeError):
                safe_json_load(temp_path, max_size=100)  # Very small limit
        finally:
            os.unlink(temp_path)

    def test_safe_json_loads_valid_string(self):
        """Test parsing valid JSON string."""
        json_string = '{"key": "value", "number": 42}'
        result = safe_json_loads(json_string)
        assert result == {"key": "value", "number": 42}

    def test_safe_json_loads_invalid_string(self):
        """Test parsing invalid JSON string."""
        with pytest.raises(ParseError, match="Invalid JSON string"):
            safe_json_loads("{ invalid json }")

    def test_safe_json_loads_string_too_large(self):
        """Test parsing JSON string that exceeds size limit."""
        large_string = '{"key": "' + "x" * 1000 + '"}'
        
        with pytest.raises(FileSizeError):
            safe_json_loads(large_string, max_size=100)

    def test_safe_json_dump_valid_data(self):
        """Test dumping valid data to JSON file."""
        test_data = {"key": "value", "number": 42}
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            safe_json_dump(test_data, temp_path)
            
            # Verify the file was written correctly
            with open(temp_path, 'r') as f:
                result = json.load(f)
            assert result == test_data
        finally:
            os.unlink(temp_path)

    def test_safe_json_dump_unserializable_data(self):
        """Test dumping unserializable data."""
        # Create an object that can't be JSON serialized
        unserializable = {"func": lambda x: x}
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ParseError, match="Unable to serialize"):
                safe_json_dump(unserializable, temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestSafeYAMLParsing:
    """Test safe YAML parsing functionality."""

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_safe_yaml_load_valid_file(self):
        """Test loading valid YAML from file."""
        yaml_content = """
key: value
number: 42
list:
  - item1
  - item2
  - item3
"""
        expected = {
            "key": "value",
            "number": 42,
            "list": ["item1", "item2", "item3"]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            result = safe_yaml_load(temp_path)
            assert result == expected
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_safe_yaml_load_invalid_yaml(self):
        """Test loading invalid YAML from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("key: value\n  invalid: indentation")
            temp_path = f.name
        
        try:
            with pytest.raises(ParseError, match="Invalid YAML"):
                safe_yaml_load(temp_path)
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_safe_yaml_loads_valid_string(self):
        """Test parsing valid YAML string."""
        yaml_string = "key: value\nnumber: 42"
        result = safe_yaml_loads(yaml_string)
        assert result == {"key": "value", "number": 42}

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_safe_yaml_loads_string_too_large(self):
        """Test parsing YAML string that exceeds size limit."""
        large_string = "key: " + "x" * 1000
        
        with pytest.raises(FileSizeError):
            safe_yaml_loads(large_string, max_size=100)

    def test_yaml_functions_without_pyyaml(self):
        """Test YAML functions when PyYAML is not available."""
        with patch('ocode_python.utils.safe_parser.YAML_AVAILABLE', False):
            with pytest.raises(ParseError, match="PyYAML is not installed"):
                safe_yaml_load("test.yaml")
            
            with pytest.raises(ParseError, match="PyYAML is not installed"):
                safe_yaml_loads("key: value")
            
            with pytest.raises(ParseError, match="PyYAML is not installed"):
                safe_yaml_dump({"key": "value"}, "test.yaml")


class TestStreamingParsing:
    """Test streaming parsing functionality."""

    def test_stream_json_objects_valid_lines(self):
        """Test streaming JSON objects from valid JSON Lines file."""
        json_lines = [
            '{"id": 1, "name": "Alice"}',
            '{"id": 2, "name": "Bob"}',
            '{"id": 3, "name": "Charlie"}'
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for line in json_lines:
                f.write(line + '\n')
            temp_path = f.name
        
        try:
            results = list(stream_json_objects(temp_path))
            expected = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"}
            ]
            assert results == expected
        finally:
            os.unlink(temp_path)

    def test_stream_json_objects_with_empty_lines(self):
        """Test streaming JSON objects with empty lines."""
        content = '''{"id": 1, "name": "Alice"}

{"id": 2, "name": "Bob"}

'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            results = list(stream_json_objects(temp_path))
            expected = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
            assert results == expected
        finally:
            os.unlink(temp_path)

    def test_stream_json_objects_with_invalid_lines(self):
        """Test streaming JSON objects with some invalid lines."""
        content = '''{"id": 1, "name": "Alice"}
{ invalid json }
{"id": 2, "name": "Bob"}'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            results = list(stream_json_objects(temp_path))
            # Should skip invalid line and continue
            expected = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
            assert results == expected
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_stream_yaml_documents(self):
        """Test streaming YAML documents."""
        yaml_content = """---
name: Document 1
type: config
---
name: Document 2
type: data
items:
  - a
  - b
  - c
---
name: Document 3
type: simple
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            results = list(stream_yaml_documents(temp_path))
            assert len(results) == 3
            assert results[0]["name"] == "Document 1"
            assert results[1]["name"] == "Document 2"
            assert results[1]["items"] == ["a", "b", "c"]
            assert results[2]["name"] == "Document 3"
        finally:
            os.unlink(temp_path)


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_load_json_convenience(self):
        """Test load_json convenience function."""
        test_data = {"test": "data"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name
        
        try:
            result = load_json(temp_path)
            assert result == test_data
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_load_yaml_convenience(self):
        """Test load_yaml convenience function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("test: data\nnumber: 42")
            temp_path = f.name
        
        try:
            result = load_yaml(temp_path)
            assert result == {"test": "data", "number": 42}
        finally:
            os.unlink(temp_path)

    def test_parse_json_convenience(self):
        """Test parse_json convenience function."""
        result = parse_json('{"test": "data"}')
        assert result == {"test": "data"}

    @pytest.mark.skipif(not YAML_AVAILABLE, reason="PyYAML not available")
    def test_parse_yaml_convenience(self):
        """Test parse_yaml convenience function."""
        result = parse_yaml("test: data\nnumber: 42")
        assert result == {"test": "data", "number": 42}


class TestConstants:
    """Test module constants."""

    def test_default_size_limits(self):
        """Test that default size limits are reasonable."""
        assert DEFAULT_JSON_MAX_SIZE == 50 * 1024 * 1024  # 50MB
        assert DEFAULT_YAML_MAX_SIZE == 10 * 1024 * 1024  # 10MB
        assert DEFAULT_JSON_MAX_SIZE > DEFAULT_YAML_MAX_SIZE  # JSON limit should be higher


class TestErrorClasses:
    """Test custom error classes."""

    def test_file_size_error_attributes(self):
        """Test FileSizeError attributes."""
        error = FileSizeError("Test message", file_size=1000, max_size=500)
        assert str(error) == "Test message"
        assert error.file_size == 1000
        assert error.max_size == 500

    def test_parse_error_attributes(self):
        """Test ParseError attributes."""
        original = ValueError("original error")
        error = ParseError("Test message", original_error=original)
        assert str(error) == "Test message"
        assert error.original_error is original

    def test_parse_error_without_original(self):
        """Test ParseError without original error."""
        error = ParseError("Test message")
        assert str(error) == "Test message"
        assert error.original_error is None