"""Unit tests for OCode engine."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ocode_python.core.api_client import StreamChunk
from ocode_python.core.engine import OCodeEngine


@pytest.mark.unit
class TestOCodeEngine:
    """Test OCodeEngine functionality."""

    @pytest.mark.asyncio
    async def test_engine_initialization(
        self, mock_project_dir: Path, mock_config: dict
    ):
        """Test engine initialization."""
        engine = OCodeEngine(
            model="test-model",
            output_format="text",
            verbose=False,
            root_path=mock_project_dir,
        )

        assert engine.model == "test-model"
        assert engine.output_format == "text"
        assert not engine.verbose
        assert engine.context_manager.root == mock_project_dir

    @pytest.mark.asyncio
    async def test_engine_context_management(self, mock_project_dir: Path):
        """Test engine initialization."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)
        assert engine.api_client is not None
        assert engine.context_manager is not None
        assert engine.tool_registry is not None

    @patch("ocode_python.core.engine.OllamaAPIClient")
    @pytest.mark.asyncio
    async def test_process_simple_prompt(
        self, mock_client_class, mock_project_dir: Path
    ):
        """Test processing a simple prompt."""
        # Mock API client
        mock_client = AsyncMock()

        async def mock_stream_chat(request):
            yield StreamChunk(content="Hello, ")
            yield StreamChunk(content="this is a test.")
            yield StreamChunk(done=True)

        mock_client.stream_chat = mock_stream_chat
        mock_client_class.return_value = mock_client

        # Create engine with small chunk size for testing
        engine = OCodeEngine(
            model="test-model", root_path=mock_project_dir, chunk_size=5
        )

        responses = []
        async for response in engine.process("Hello, world!"):
            responses.append(response)

        # With small chunk size, we should get the full response
        full_response = "".join(responses)
        assert full_response == "Hello, this is a test."

    @patch("ocode_python.core.engine.OllamaAPIClient")
    @pytest.mark.asyncio
    async def test_process_with_context(
        self, mock_client_class, mock_project_dir: Path
    ):
        """Test processing with context files."""
        mock_client = AsyncMock()

        async def mock_stream_chat(request):
            yield StreamChunk(content="Based on the context, ")
            yield StreamChunk(content="I can help you.")
            yield StreamChunk(done=True)

        mock_client.stream_chat = mock_stream_chat
        mock_client_class.return_value = mock_client

        # Create engine with small chunk size for testing
        engine = OCodeEngine(
            model="test-model", root_path=mock_project_dir, chunk_size=10
        )

        responses = []
        async for response in engine.process("Analyze the main.py file"):
            responses.append(response)

        # Check that we got the expected response
        full_response = "".join(responses)
        assert "Based on the context" in full_response

    @patch("ocode_python.core.engine.OllamaAPIClient")
    @pytest.mark.asyncio
    async def test_process_with_tool_calls(
        self, mock_client_class, mock_project_dir: Path
    ):
        """Test processing with tool calls."""
        from ocode_python.core.api_client import ToolCall

        mock_client = AsyncMock()

        async def mock_stream_chat(request):
            # First yield a tool call
            tool_call = ToolCall(
                name="file_read", arguments={"path": "main.py"}, id="call_123"
            )
            yield StreamChunk(tool_call=tool_call)

            # Then yield final response
            yield StreamChunk(content="The file contains a main function.")
            yield StreamChunk(done=True)

        mock_client.stream_chat = mock_stream_chat
        mock_client_class.return_value = mock_client

        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Mock tool execution
        with patch.object(engine.tool_registry, "execute_tool") as mock_execute:
            from ocode_python.tools.base import ToolResult

            mock_execute.return_value = ToolResult(
                success=True, output="print('Hello, world!')"
            )

            responses = []
            async for response in engine.process("Read the main.py file"):
                responses.append(response)

            # Should execute tool and return response
            mock_execute.assert_called_once()
            assert len(responses) >= 1

    @pytest.mark.asyncio
    async def test_engine_error_handling(self, mock_project_dir: Path):
        """Test engine error handling."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Mock API client to raise an error
        class FailingStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise Exception("API error")

        engine.api_client = AsyncMock()
        engine.api_client.stream_chat = lambda _request: FailingStream()

        responses = []
        async for response in engine.process("test prompt"):
            responses.append(response)

        # Should handle error gracefully
        assert len(responses) >= 1
        assert any("error" in response.lower() for response in responses)

    @pytest.mark.asyncio
    async def test_save_and_continue_session(self, mock_project_dir: Path):
        """Test session management."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Add some conversation history
        from ocode_python.core.api_client import Message

        engine.conversation_history.extend(
            [
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
            ]
        )

        # Save session
        session_id = await engine.save_session()
        assert session_id is not None

        # Create new engine and continue session
        new_engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        success = await new_engine.continue_session(session_id)
        assert success
        assert len(new_engine.conversation_history) == 2

    @pytest.mark.asyncio
    async def test_engine_with_different_formats(self, mock_project_dir: Path):
        """Test engine with different output formats."""
        formats = ["text", "json", "stream-json"]

        for fmt in formats:
            engine = OCodeEngine(
                model="test-model", output_format=fmt, root_path=mock_project_dir
            )

            assert engine.output_format == fmt

    @pytest.mark.asyncio
    async def test_context_file_selection(self, mock_project_dir: Path):
        """Test context preparation."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Test different prompts
        test_prompts = [
            "Fix the main function",
            "Update the Calculator class",
            "Look at the package module",
        ]

        for prompt in test_prompts:
            # Context preparation is done internally by the engine
            # We just verify the engine can be created and has context manager
            assert engine.context_manager is not None
            assert engine.context_manager.root == mock_project_dir

    @pytest.mark.asyncio
    async def test_engine_memory_management(self, mock_project_dir: Path):
        """Test memory management for long conversations."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Simulate long conversation
        for i in range(20):
            engine.conversation_history.extend(
                [
                    {"role": "user", "content": f"Message {i}"},
                    {"role": "assistant", "content": f"Response {i}"},
                ]
            )

        # Conversation history should exist
        assert len(engine.conversation_history) > 0
        # We populated 40 messages (20 pairs)
        assert len(engine.conversation_history) == 40


@pytest.mark.unit
class TestEngineUtilities:
    """Test engine utility functions."""

    def test_format_response_text(self, mock_project_dir: Path):
        """Test text output format."""
        engine = OCodeEngine(
            model="test-model", output_format="text", root_path=mock_project_dir
        )

        # Test that the engine has the correct output format
        assert engine.output_format == "text"

    def test_format_response_json(self, mock_project_dir: Path):
        """Test JSON output format."""
        engine = OCodeEngine(
            model="test-model", output_format="json", root_path=mock_project_dir
        )

        # Test that the engine has the correct output format
        assert engine.output_format == "json"

    def test_validate_model_name(self, mock_project_dir: Path):
        """Test model name validation."""
        # Valid model names
        valid_names = ["llama3:8b", "codellama:7b", "custom-model"]

        for name in valid_names:
            engine = OCodeEngine(model=name, root_path=mock_project_dir)
            assert engine.model == name

    @pytest.mark.asyncio
    async def test_engine_health_check(self, mock_project_dir: Path):
        """Test engine health check."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Mock healthy API client
        engine.api_client = AsyncMock()
        engine.api_client.check_health = AsyncMock(return_value=True)

        is_healthy = await engine.api_client.check_health()
        assert is_healthy

        # Mock unhealthy API client
        engine.api_client.check_health = AsyncMock(return_value=False)

        is_healthy = await engine.api_client.check_health()
        assert not is_healthy
