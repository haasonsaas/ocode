"""Unit tests for Ollama API client."""

from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from ocode_python.core.api_client import (
    CompletionRequest,
    Message,
    OllamaAPIClient,
    StreamChunk,
    ToolCall,
)


@pytest.mark.unit
class TestOllamaAPIClient:
    """Test OllamaAPIClient functionality."""

    def test_init_default_host(self):
        """Test client initialization with default host."""
        client = OllamaAPIClient()
        assert client.base_url == "http://localhost:11434"

    def test_init_custom_host(self):
        """Test client initialization with custom host."""
        client = OllamaAPIClient("http://custom-host:8080")
        assert client.base_url == "http://custom-host:8080"

    def test_init_with_env_var(self):
        """Test client initialization with environment variable."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://env-host:9090"}):
            client = OllamaAPIClient()
            assert client.base_url == "http://env-host:9090"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with OllamaAPIClient() as client:
            assert client.session is not None
            assert not client.session.closed

    def test_parse_chunk_content(self):
        """Test parsing of content chunks."""
        client = OllamaAPIClient()

        data = {
            "message": {"content": "Hello, world!"},
            "done": False,
            "model": "test-model",
        }

        chunk = client._parse_chunk(data)
        assert chunk.content == "Hello, world!"
        assert not chunk.done
        assert chunk.model == "test-model"
        assert chunk.type == "content"

    def test_parse_chunk_tool_call(self):
        """Test parsing of tool call chunks."""
        client = OllamaAPIClient()

        data = {
            "message": {
                "tool_calls": [
                    {
                        "id": "call_123",
                        "function": {
                            "name": "test_tool",
                            "arguments": {"param": "value"},
                        },
                    }
                ]
            },
            "done": False,
        }

        chunk = client._parse_chunk(data)
        assert chunk.tool_call is not None
        assert chunk.tool_call.name == "test_tool"
        assert chunk.tool_call.arguments == {"param": "value"}
        assert chunk.tool_call.id == "call_123"
        assert chunk.type == "tool_call"

    def test_parse_chunk_done(self):
        """Test parsing of done chunks."""
        client = OllamaAPIClient()

        data = {"done": True}

        chunk = client._parse_chunk(data)
        assert chunk.done
        assert chunk.type == "done"

    @pytest.mark.asyncio
    async def test_stream_chat_success(self):
        """Test successful streaming chat."""
        client = OllamaAPIClient()

        # Mock response data
        response_lines = [
            b'{"message": {"content": "Hello"}, "done": false}\n',
            b'{"message": {"content": " world"}, "done": false}\n',
            b'{"done": true}\n',
        ]

        # Create a proper async iterator
        async def async_iter(items):
            for item in items:
                yield item

        # Mock aiohttp session and response
        mock_response = AsyncMock()
        mock_response.content = async_iter(response_lines)
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.closed = False
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = Mock(return_value=mock_context_manager)

        # Patch the ClientSession to return our mock
        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            request = CompletionRequest(
                model="test-model", messages=[{"role": "user", "content": "Hello"}]
            )

            chunks = []
            async for chunk in client.stream_chat(request):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " world"
            assert chunks[2].done

    @pytest.mark.asyncio
    async def test_stream_chat_connection_error(self):
        """Test handling of connection errors."""
        client = OllamaAPIClient()

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )
        client.session = mock_session

        request = CompletionRequest(
            model="test-model", messages=[{"role": "user", "content": "Hello"}]
        )

        with pytest.raises(ConnectionError, match="Failed to connect to Ollama"):
            async for chunk in client.stream_chat(request):
                pass

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        """Test successful model listing."""
        client = OllamaAPIClient()

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(
            return_value={
                "models": [
                    {"name": "llama3:8b", "size": 4000000000},
                    {"name": "codellama:7b", "size": 3500000000},
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.closed = False
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = Mock(return_value=mock_context_manager)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            models = await client.list_models()

            assert len(models) == 2
            assert models[0]["name"] == "llama3:8b"
            assert models[1]["name"] == "codellama:7b"

    @pytest.mark.asyncio
    async def test_check_health_success(self):
        """Test successful health check."""
        client = OllamaAPIClient()

        mock_response = AsyncMock()
        mock_response.status = 200

        # Create a proper async context manager mock
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.get = Mock(return_value=mock_context_manager)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            is_healthy = await client.check_health()
            assert is_healthy

    @pytest.mark.asyncio
    async def test_check_health_failure(self):
        """Test health check failure."""
        client = OllamaAPIClient()

        mock_session = AsyncMock()
        mock_session.closed = False

        class FailingContext:
            async def __aenter__(self):
                raise aiohttp.ClientError("Connection failed")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        mock_session.get = Mock(return_value=FailingContext())

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            is_healthy = await client.check_health()
            assert not is_healthy

    @pytest.mark.asyncio
    async def test_pull_model_success(self):
        """Test successful model pull."""
        client = OllamaAPIClient()

        progress_lines = [
            b'{"status": "pulling manifest"}\n',
            b'{"status": "downloading", "completed": 1000, "total": 2000}\n',
            b'{"status": "success"}\n',
        ]

        # Create a proper async iterator
        async def async_iter(items):
            for item in items:
                yield item

        mock_response = AsyncMock()
        mock_response.content = async_iter(progress_lines)
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.closed = False
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = Mock(return_value=mock_context_manager)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            progress_updates = []
            async for progress in client.pull_model("test-model"):
                progress_updates.append(progress)

            assert len(progress_updates) == 3
            assert progress_updates[0]["status"] == "pulling manifest"
            assert progress_updates[1]["status"] == "downloading"
            assert progress_updates[2]["status"] == "success"

    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self):
        """Test successful embedding generation."""
        client = OllamaAPIClient()

        mock_response = AsyncMock()
        mock_response.json = AsyncMock(
            return_value={"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
        )
        mock_response.raise_for_status = Mock()

        mock_session = AsyncMock()
        mock_session.closed = False
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = Mock(return_value=mock_context_manager)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value = mock_session

            embedding = await client.generate_embeddings("test-model", "Hello world")

            assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


@pytest.mark.unit
class TestDataClasses:
    """Test data classes and structures."""

    def test_message_to_dict(self):
        """Test Message to_dict conversion."""
        message = Message("user", "Hello, world!")
        expected = {"role": "user", "content": "Hello, world!"}
        assert message.to_dict() == expected

    def test_completion_request_dict(self):
        """Test CompletionRequest dict conversion."""
        request = CompletionRequest(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )

        data = request.dict()
        assert data["model"] == "test-model"
        assert data["stream"] is True
        assert len(data["messages"]) == 1

    def test_stream_chunk_properties(self):
        """Test StreamChunk properties."""
        # Content chunk
        chunk = StreamChunk(content="Hello")
        assert chunk.type == "content"

        # Tool call chunk
        tool_call = ToolCall("test_tool", {"param": "value"})
        chunk = StreamChunk(tool_call=tool_call)
        assert chunk.type == "tool_call"

        # Done chunk
        chunk = StreamChunk(done=True)
        assert chunk.type == "done"

        # Unknown chunk
        chunk = StreamChunk()
        assert chunk.type == "unknown"
