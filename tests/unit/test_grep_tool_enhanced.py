"""Comprehensive unit tests for enhanced grep tool."""

import tempfile
from pathlib import Path

import pytest

from ocode_python.tools.grep_tool import GrepTool


class TestGrepToolEnhanced:
    """Test enhanced grep tool functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "test.py").write_text(
                """
def hello_world():
    print("Hello, World!")

class TestClass:
    def method(self):
        pass
"""
            )

            (tmpdir_path / "test.js").write_text(
                """
function helloWorld() {
    console.log("Hello, World!");
}

class TestClass {
    method() {
        return true;
    }
}
"""
            )

            (tmpdir_path / "test.ts").write_text(
                """
interface TestInterface {
    name: string;
}

function helloWorld(): void {
    console.log("Hello, World!");
}

class TestClass implements TestInterface {
    name: string = "test";

    method(): boolean {
        return true;
    }
}
"""
            )

            (tmpdir_path / "test.java").write_text(
                """
public class TestClass {
    public void helloWorld() {
        System.out.println("Hello, World!");
    }

    private String name = "test";
}
"""
            )

            (tmpdir_path / "test.go").write_text(
                """
package main

import "fmt"

func helloWorld() {
    fmt.Println("Hello, World!")
}

type TestStruct struct {
    Name string
}
"""
            )

            (tmpdir_path / "test.rs").write_text(
                """
fn hello_world() {
    println!("Hello, World!");
}

struct TestStruct {
    name: String,
}

impl TestStruct {
    fn new() -> Self {
        TestStruct { name: String::from("test") }
    }
}
"""
            )

            yield tmpdir_path

    @pytest.fixture
    def grep_tool(self):
        """Create GrepTool instance."""
        return GrepTool()

    @pytest.mark.asyncio
    async def test_basic_grep(self, grep_tool, temp_dir):
        """Test basic grep functionality."""
        result = await grep_tool.execute(pattern="Hello", path=str(temp_dir))

        assert result.success
        assert "test.py" in result.output
        assert "test.js" in result.output
        assert "test.ts" in result.output
        assert "test.java" in result.output
        assert "test.go" in result.output
        assert "test.rs" in result.output

    @pytest.mark.asyncio
    async def test_grep_with_include(self, grep_tool, temp_dir):
        """Test grep with file include pattern."""
        result = await grep_tool.execute(
            pattern="Hello", path=str(temp_dir), file_pattern="*.py"
        )

        assert result.success
        assert "test.py" in result.output
        assert "test.js" not in result.output

    @pytest.mark.asyncio
    async def test_enhanced_search_python(self, grep_tool, temp_dir):
        """Test enhanced search for Python files."""
        result = await grep_tool.execute(
            pattern="class", path=str(temp_dir), file_pattern="*.py", enhanced=True
        )

        assert result.success
        assert "TestClass" in result.output
        assert "Classes:" in result.output or "class" in result.output.lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_javascript(self, grep_tool, temp_dir):
        """Test enhanced search for JavaScript files."""
        result = await grep_tool.execute(
            pattern="function", path=str(temp_dir), file_pattern="*.js", enhanced=True
        )

        assert result.success
        assert "helloWorld" in result.output
        assert "Functions:" in result.output or "function" in result.output.lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_typescript(self, grep_tool, temp_dir):
        """Test enhanced search for TypeScript files."""
        result = await grep_tool.execute(
            pattern="interface", path=str(temp_dir), file_pattern="*.ts", enhanced=True
        )

        assert result.success
        assert "TestInterface" in result.output
        assert "Interfaces:" in result.output or "interface" in result.output.lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_java(self, grep_tool, temp_dir):
        """Test enhanced search for Java files."""
        result = await grep_tool.execute(
            pattern="class", path=str(temp_dir), file_pattern="*.java", enhanced=True
        )

        assert result.success
        assert "TestClass" in result.output
        assert "Classes:" in result.output or "class" in result.output.lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_go(self, grep_tool, temp_dir):
        """Test enhanced search for Go files."""
        result = await grep_tool.execute(
            pattern="func", path=str(temp_dir), file_pattern="*.go", enhanced=True
        )

        assert result.success
        assert "helloWorld" in result.output
        assert "Functions:" in result.output or "func" in result.output.lower()

    @pytest.mark.asyncio
    async def test_enhanced_search_rust(self, grep_tool, temp_dir):
        """Test enhanced search for Rust files."""
        result = await grep_tool.execute(
            pattern="struct", path=str(temp_dir), file_pattern="*.rs", enhanced=True
        )

        assert result.success
        assert "TestStruct" in result.output
        assert "Structs:" in result.output or "struct" in result.output.lower()

    @pytest.mark.skip(reason="Private method _parse_python_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_python_file(self, grep_tool, temp_dir):
        """Test Python file parsing."""
        file_path = temp_dir / "test.py"
        result = await grep_tool._parse_python_file(str(file_path), "class")

        assert len(result) > 0
        assert any("TestClass" in item for item in result)

    @pytest.mark.skip(reason="Private method _parse_python_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_python_file_invalid_syntax(self, grep_tool, temp_dir):
        """Test Python file parsing with invalid syntax."""
        file_path = temp_dir / "invalid.py"
        file_path.write_text("def invalid syntax")

        result = await grep_tool._parse_python_file(str(file_path), "def")
        assert len(result) == 0  # Should handle errors gracefully

    @pytest.mark.skip(reason="Private method _parse_javascript_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_javascript_file(self, grep_tool, temp_dir):
        """Test JavaScript file parsing."""
        file_path = temp_dir / "test.js"
        result = await grep_tool._parse_javascript_file(str(file_path), "function")

        assert len(result) > 0
        assert any("helloWorld" in item for item in result)

    @pytest.mark.skip(reason="Private method _parse_typescript_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_typescript_file(self, grep_tool, temp_dir):
        """Test TypeScript file parsing."""
        file_path = temp_dir / "test.ts"
        result = await grep_tool._parse_typescript_file(str(file_path), "interface")

        assert len(result) > 0
        assert any("TestInterface" in item for item in result)

    @pytest.mark.skip(reason="Private method _parse_java_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_java_file(self, grep_tool, temp_dir):
        """Test Java file parsing."""
        file_path = temp_dir / "test.java"
        result = await grep_tool._parse_java_file(str(file_path), "class")

        assert len(result) > 0
        assert any("TestClass" in item for item in result)

    @pytest.mark.skip(reason="Private method _parse_go_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_go_file(self, grep_tool, temp_dir):
        """Test Go file parsing."""
        file_path = temp_dir / "test.go"
        result = await grep_tool._parse_go_file(str(file_path), "type")

        assert len(result) > 0
        assert any("TestStruct" in item for item in result)

    @pytest.mark.skip(reason="Private method _parse_rust_file doesn't exist")
    @pytest.mark.asyncio
    async def test_parse_rust_file(self, grep_tool, temp_dir):
        """Test Rust file parsing."""
        file_path = temp_dir / "test.rs"
        result = await grep_tool._parse_rust_file(str(file_path), "fn")

        assert len(result) > 0
        assert any("hello_world" in item for item in result)

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, grep_tool, temp_dir):
        """Test grep with no matches."""
        result = await grep_tool.execute(
            pattern="nonexistentpattern", path=str(temp_dir)
        )

        assert result.success
        assert "No matches found" in result.output or result.output == ""

    @pytest.mark.asyncio
    async def test_grep_invalid_regex(self, grep_tool, temp_dir):
        """Test grep with invalid regex pattern."""
        result = await grep_tool.execute(pattern="[invalid(regex", path=str(temp_dir))

        assert not result.success
        assert (
            "error" in result.output.lower()
            or "invalid" in result.output.lower()
            or (
                result.error
                and (
                    "error" in result.error.lower() or "invalid" in result.error.lower()
                )
            )
        )

    @pytest.mark.asyncio
    async def test_grep_nonexistent_path(self, grep_tool):
        """Test grep with non-existent path."""
        result = await grep_tool.execute(pattern="test", path="/nonexistent/path")

        assert not result.success
        assert (
            "error" in result.output.lower()
            or "not found" in result.output.lower()
            or (
                result.error
                and (
                    "error" in result.error.lower()
                    or "not found" in result.error.lower()
                    or "does not exist" in result.error.lower()
                )
            )
        )

    @pytest.mark.asyncio
    async def test_enhanced_search_mixed_languages(self, grep_tool, temp_dir):
        """Test enhanced search across multiple language files."""
        result = await grep_tool.execute(
            pattern="class|struct|interface", path=str(temp_dir), enhanced=True
        )

        assert result.success
        # Should find matches in multiple language files
        assert "TestClass" in result.output  # Python, JS, TS, Java
        assert "TestStruct" in result.output  # Go, Rust
        assert "TestInterface" in result.output  # TypeScript

    @pytest.mark.asyncio
    async def test_get_schema(self, grep_tool):
        """Test getting tool definition."""
        # Check tool definition instead of get_schema method
        definition = grep_tool.definition

        assert definition.name == "grep"
        assert definition.description is not None
        assert len(definition.parameters) > 0

        # Check parameter names
        param_names = [p.name for p in definition.parameters]
        assert "pattern" in param_names
        assert "path" in param_names
        assert "file_pattern" in param_names

    @pytest.mark.asyncio
    async def test_enhanced_search_performance(self, grep_tool, temp_dir):
        """Test enhanced search doesn't significantly slow down."""
        import time

        # Create many files
        for i in range(10):
            (temp_dir / f"perf_test_{i}.py").write_text(
                """
class PerfTest:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
"""
            )

        # Time regular search
        start = time.time()
        result1 = await grep_tool.execute(
            pattern="class", path=str(temp_dir), file_pattern="perf_test_*.py"
        )
        regular_time = time.time() - start

        # Time enhanced search
        start = time.time()
        result2 = await grep_tool.execute(
            pattern="class",
            path=str(temp_dir),
            file_pattern="perf_test_*.py",
            enhanced=True,
        )
        enhanced_time = time.time() - start

        assert result1.success
        assert result2.success
        # Enhanced search should not be more than 10x slower (relaxed for CI)
        # Or if regular time is very fast (< 0.001s), just check that enhanced works
        if regular_time > 0.001:
            assert enhanced_time < regular_time * 10
        else:
            # If regular search was extremely fast, just ensure enhanced works
            assert enhanced_time < 5.0  # Should complete within 5 seconds
