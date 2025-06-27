"""
Integration tests for OCode engine.
"""

from pathlib import Path

import pytest

from ocode_python.core.api_client import StreamChunk
from ocode_python.core.engine import OCodeEngine


@pytest.mark.integration
class TestOCodeEngineIntegration:
    """Test OCode engine integration."""

    @pytest.mark.asyncio
    async def test_engine_process_simple_query(self, ocode_engine: OCodeEngine):
        """Test processing a simple query."""
        query = "What files are in this project?"

        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)

        # Should get some response
        assert len(responses) > 0

        # Should have analyzed some files
        assert ocode_engine.current_context is not None
        assert len(ocode_engine.current_context.files) > 0

    @pytest.mark.asyncio
    async def test_engine_process_with_tool_call(self, ocode_engine: OCodeEngine):
        """Test processing query that should trigger tool calls."""

        # Mock tool call in API response
        async def mock_stream_with_tool(*args, **kwargs):
            from ocode_python.core.api_client import ToolCall

            chunks = [
                StreamChunk(content="I'll help you read that file. "),
                StreamChunk(tool_call=ToolCall("file_read", {"path": "main.py"})),
                StreamChunk(content="The file contains a main function."),
                StreamChunk(done=True),
            ]

            for chunk in chunks:
                yield chunk

        ocode_engine.api_client.stream_chat = mock_stream_with_tool

        query = "Read the main.py file and explain what it does"

        responses = []
        all_content = ""

        async for chunk in ocode_engine.process(query):
            responses.append(chunk)
            all_content += str(chunk)

        assert len(responses) > 0
        # The mocked response should contain the expected content
        assert "help you read that file" in all_content or "file contains" in all_content

    @pytest.mark.asyncio
    async def test_engine_conversation_history(self, ocode_engine: OCodeEngine):
        """Test conversation history management."""
        # First query
        query1 = "Hello, what is this project about?"

        responses1 = []
        async for chunk in ocode_engine.process(query1):
            responses1.append(chunk)

        assert len(ocode_engine.conversation_history) == 2  # User + assistant

        # Second query
        query2 = "Can you tell me more about the main file?"

        responses2 = []
        async for chunk in ocode_engine.process(query2):
            responses2.append(chunk)

        assert len(ocode_engine.conversation_history) == 4  # 2 exchanges

    @pytest.mark.asyncio
    async def test_engine_context_building(
        self, ocode_engine: OCodeEngine, mock_project_dir: Path
    ):
        """Test context building with real project files."""
        query = "Analyze the Python files in this project"

        # Process query to build context
        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)

        context = ocode_engine.current_context
        assert context is not None

        # Should have found Python files
        python_files = [f for f in context.files.keys() if f.suffix == ".py"]
        assert len(python_files) > 0

        # Should have file info
        assert len(context.file_info) > 0

        # Should have some symbols
        assert len(context.symbols) > 0

        # Check project root
        assert context.project_root == mock_project_dir

    @pytest.mark.asyncio
    async def test_engine_error_handling(self, ocode_engine: OCodeEngine):
        """Test engine error handling."""

        # Mock API client to raise an error
        async def mock_stream_error(*args, **kwargs):
            # Make it an async generator that raises an error
            if False:
                yield  # Make it a generator
            raise Exception("API Error")

        ocode_engine.api_client.stream_chat = mock_stream_error

        query = "This should cause an error"

        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)

        # Should get error response
        assert len(responses) > 0
        error_found = any("Error" in str(chunk) for chunk in responses)
        assert error_found

    def test_engine_status(self, ocode_engine: OCodeEngine):
        """Test engine status reporting."""
        status = ocode_engine.get_status()

        assert "model" in status
        assert "context_files" in status
        assert "conversation_length" in status
        assert "tools_available" in status
        assert "project_root" in status

        assert status["model"] == "test-model"
        assert status["tools_available"] > 0

    def test_engine_clear_context(self, ocode_engine: OCodeEngine):
        """Test clearing engine context."""
        # Add some conversation history
        from ocode_python.core.api_client import Message

        ocode_engine.conversation_history.append(Message("user", "test"))

        # Set current context
        from ocode_python.core.context_manager import ProjectContext

        ocode_engine.current_context = ProjectContext(
            files={},
            file_info={},
            dependencies={},
            symbols={},
            project_root=Path("/test"),
        )

        # Clear context
        ocode_engine.clear_context()

        assert ocode_engine.current_context is None
        assert len(ocode_engine.conversation_history) == 0


@pytest.mark.integration
@pytest.mark.slow
class TestEngineWithRealFiles:
    """Test engine with real file operations."""

    @pytest.mark.asyncio
    async def test_engine_file_analysis(self, mock_project_dir: Path):
        """Test engine with real file analysis."""
        engine = OCodeEngine(model="test-model", root_path=mock_project_dir)

        # Mock API client
        async def mock_stream(*args, **kwargs):
            chunks = [
                StreamChunk(
                    content="I can see this is a Python project with several modules."
                ),
                StreamChunk(done=True),
            ]
            for chunk in chunks:
                yield chunk

        engine.api_client.stream_chat = mock_stream

        query = "Analyze the structure of this Python project"

        responses = []
        async for chunk in engine.process(query):
            responses.append(chunk)

        # Should have analyzed files
        assert engine.current_context is not None
        assert len(engine.current_context.files) > 0

        # Should have found Python files
        python_files = [
            f for f in engine.current_context.files.keys() if f.suffix == ".py"
        ]
        assert len(python_files) >= 3  # main.py, utils.py, test_utils.py

        # Should have extracted symbols
        assert len(engine.current_context.symbols) > 0

    @pytest.mark.asyncio
    async def test_engine_with_git_info(self, mock_git_repo: Path):
        """Test engine with git repository."""
        engine = OCodeEngine(model="test-model", root_path=mock_git_repo)

        # Mock API client
        async def mock_stream(*args, **kwargs):
            chunks = [
                StreamChunk(content="This is a git repository. "),
                StreamChunk(
                    content="I can see the current branch and commit information."
                ),
                StreamChunk(done=True),
            ]
            for chunk in chunks:
                yield chunk

        engine.api_client.stream_chat = mock_stream

        query = "What's the current git status?"

        responses = []
        async for chunk in engine.process(query):
            responses.append(chunk)

        # Should have git information
        assert engine.current_context is not None
        assert engine.current_context.git_info is not None
        assert "branch" in engine.current_context.git_info
        assert "commit" in engine.current_context.git_info


@pytest.mark.integration
class TestEngineSessionManagement:
    """Test engine session management."""

    @pytest.mark.asyncio
    async def test_save_and_load_session(
        self, ocode_engine: OCodeEngine, temp_dir: Path
    ):
        """Test saving and loading sessions."""
        # Process a query to create conversation
        query = "Hello, how are you?"

        responses = []
        async for chunk in ocode_engine.process(query):
            responses.append(chunk)

        # Save session
        session_id = await ocode_engine.save_session()
        assert session_id is not None

        # Clear current state
        ocode_engine.clear_context()

        # Load session
        loaded = await ocode_engine.continue_session(session_id)
        assert loaded

        # Should have restored conversation
        assert len(ocode_engine.conversation_history) > 0

    @pytest.mark.asyncio
    async def test_session_persistence(self, ocode_engine: OCodeEngine):
        """Test session persistence across multiple interactions."""
        # Multiple queries in sequence
        queries = [
            "What is this project?",
            "Tell me about the main.py file",
            "What functions are in utils.py?",
        ]

        for query in queries:
            responses = []
            async for chunk in ocode_engine.process(query):
                responses.append(chunk)

        # Should have cumulative conversation history
        assert (
            len(ocode_engine.conversation_history) == len(queries) * 2
        )  # User + assistant each

        # Context should be preserved
        assert ocode_engine.current_context is not None
