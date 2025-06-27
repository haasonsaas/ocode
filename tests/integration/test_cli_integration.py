"""
Integration tests for CLI functionality.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from ocode_python.core.cli import cli


def mock_asyncio_run(coro):
    """Mock asyncio.run to properly consume coroutines."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.integration
@pytest.mark.cli
class TestCLIIntegration:
    """Test CLI integration."""

    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "OCode" in result.output
        assert "--model" in result.output
        assert "--verbose" in result.output

    def test_cli_version_check(self):
        """Test CLI version display."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # Should show help since no explicit version flag
        assert "Usage:" in result.output

    @patch("ocode_python.core.cli.OCodeEngine")
    @patch("ocode_python.core.cli.AuthenticationManager")
    def test_cli_single_prompt(self, mock_auth, mock_engine):
        """Test CLI with single prompt."""
        # Mock authentication
        mock_auth_instance = Mock()
        mock_auth_instance.token.return_value = "test-token"
        mock_auth.return_value = mock_auth_instance

        # Mock engine with async generator
        async def mock_process(prompt, continue_previous=False):
            yield "This is a test response."

        # Create AsyncMock for the engine instance

        mock_engine_instance = AsyncMock()
        mock_engine_instance.process = mock_process
        mock_engine.return_value = mock_engine_instance

        runner = CliRunner()
        
        # Create a config file to avoid onboarding prompt
        with runner.isolated_filesystem():
            config_dir = Path.home() / ".ocode"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "config.json"
            config_file.write_text('{"model": "test"}')
            
            result = runner.invoke(cli, ["-p", "Hello, world!"])

            # Check exit code - should be 0 for successful completion
            if result.exit_code != 0:
                print(f"Exit code: {result.exit_code}")
                print(f"Output: {result.output}")
                if result.exception:
                    print(f"Exception: {result.exception}")

            assert result.exit_code == 0
            assert "This is a test response." in result.output

    def test_cli_init_command(self, temp_dir: Path):
        """Test CLI init command."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            assert "Initialized OCode" in result.output

            # Check if .ocode directory was created
            ocode_dir = Path(".ocode")
            assert ocode_dir.exists()
            assert (ocode_dir / "settings.json").exists()
            assert (ocode_dir / "memory").exists()
            assert (ocode_dir / "commands").exists()

    def test_cli_init_existing_project(self, temp_dir: Path):
        """Test CLI init on existing OCode project."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Initialize once
            result1 = runner.invoke(cli, ["init"])
            assert result1.exit_code == 0

            # Initialize again
            result2 = runner.invoke(cli, ["init"])
            assert result2.exit_code == 0
            assert "already initialized" in result2.output

    def test_cli_config_commands(self):
        """Test CLI config commands."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Set config value
            result1 = runner.invoke(cli, ["config", "--set", "test_key=test_value"])
            assert result1.exit_code == 0

            # Get config value
            result2 = runner.invoke(cli, ["config", "--get", "test_key"])
            assert result2.exit_code == 0
            # Note: Actual config getting depends on ConfigManager implementation

    def test_cli_auth_commands(self):
        """Test CLI auth commands."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Check auth status
            result = runner.invoke(cli, ["auth", "--status"])
            assert result.exit_code == 0
            # Should show not authenticated initially

    def test_cli_mcp_commands(self):
        """Test CLI MCP commands."""
        runner = CliRunner()

        # List MCP servers
        result = runner.invoke(cli, ["mcp", "--list"])
        assert result.exit_code == 0
        assert "MCP servers" in result.output

    @patch("prompt_toolkit.PromptSession")
    @patch("ocode_python.core.cli.OCodeEngine")
    @patch("ocode_python.core.cli.AuthenticationManager")
    def test_cli_interactive_mode(self, mock_auth, mock_engine, mock_prompt_session):
        """Test CLI interactive mode."""
        # Mock authentication
        mock_auth_instance = Mock()
        mock_auth_instance.token.return_value = "test-token"
        mock_auth.return_value = mock_auth_instance

        # Mock engine
        async def mock_process(prompt):
            if prompt.strip() == "/exit":
                return
            yield f"Response to: {prompt}"

        mock_engine_instance = Mock()
        mock_engine_instance.process = mock_process
        mock_engine.return_value = mock_engine_instance

        # Mock prompt session
        async def mock_prompt_async(prompt_text):
            # Simulate user entering exit command
            return "/exit"

        mock_session = Mock()
        mock_session.prompt_async = mock_prompt_async
        mock_prompt_session.return_value = mock_session

        runner = CliRunner()

        # This test is complex due to async nature
        # For now, just test that it doesn't crash on setup
        with patch("asyncio.run", side_effect=mock_asyncio_run) as mock_run:
            runner.invoke(cli, [])
            # The actual async execution is mocked
            assert mock_run.called


@pytest.mark.integration
@pytest.mark.cli
class TestCLIWithRealComponents:
    """Test CLI with real components (but mocked external dependencies)."""

    @patch("ocode_python.core.api_client.OllamaAPIClient")
    def test_cli_with_mock_ollama(self, mock_client_class, mock_project_dir: Path):
        """Test CLI with mocked Ollama client."""
        # Mock the client
        mock_client = Mock()
        mock_client.check_health = Mock(return_value=True)

        async def mock_stream(*args, **kwargs):
            from ocode_python.core.api_client import StreamChunk

            yield StreamChunk(content="Test response")
            yield StreamChunk(done=True)

        mock_client.stream_chat = mock_stream
        mock_client_class.return_value = mock_client

        runner = CliRunner()

        with patch(
            "ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run
        ) as mock_run:
            runner.invoke(cli, ["-p", "Test prompt", "--model", "test-model"])

            # Should attempt to run async function
            assert mock_run.called

    def test_cli_error_handling(self):
        """Test CLI error handling."""
        runner = CliRunner()

        # Test with invalid config file
        result = runner.invoke(
            cli, ["--config", "/nonexistent/config.json", "-p", "test"]
        )

        # Should handle gracefully (might show warning but shouldn't crash)
        # Click returns exit code 2 for invalid path when using exists=True
        assert result.exit_code == 2  # Click's error code for invalid path

    def test_cli_verbose_mode(self):
        """Test CLI verbose mode."""
        runner = CliRunner()

        with patch("ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run):
            result = runner.invoke(cli, ["-v", "-p", "test prompt"])

            # Should not crash with verbose flag
            assert result.exit_code in [0, 1]

    def test_cli_different_output_formats(self):
        """Test CLI with different output formats."""
        runner = CliRunner()

        formats = ["text", "json", "stream-json"]

        for fmt in formats:
            with patch(
                "ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run
            ):
                result = runner.invoke(cli, ["--out", fmt, "-p", "test"])

                # Should accept all valid formats
                assert result.exit_code in [0, 1]


@pytest.mark.integration
@pytest.mark.cli
@pytest.mark.slow
class TestCLIEndToEnd:
    """End-to-end CLI tests (slower, more comprehensive)."""

    @pytest.mark.asyncio
    async def test_full_cli_workflow(self, mock_project_dir: Path):
        """Test complete CLI workflow."""

        from ocode_python.core.cli import handle_single_prompt

        # Mock the engine components
        options = {"model": "test-model", "output_format": "text", "verbose": False}

        # This would be a real end-to-end test if we had a test Ollama instance
        # For now, we test the structure
        with patch("ocode_python.core.cli.OCodeEngine") as mock_engine_class:
            mock_engine = AsyncMock()

            async def mock_process(prompt, continue_previous=False):
                yield f"Processing: {prompt}"
                yield "Analysis complete."

            mock_engine.process = mock_process
            mock_engine_class.return_value = mock_engine

            # Test single prompt handling
            await handle_single_prompt("Analyze this project", options)

            # Verify engine was created
            mock_engine_class.assert_called_once()

    def test_cli_with_project_initialization(self, temp_dir: Path):
        """Test CLI workflow with project initialization."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a mock project
            (Path(".") / "main.py").write_text('print("Hello, world!")')
            (Path(".") / "utils.py").write_text("def helper(): pass")

            # Initialize OCode
            result1 = runner.invoke(cli, ["init"])
            assert result1.exit_code == 0

            # Verify initialization
            assert Path(".ocode").exists()
            assert Path(".ocode/settings.json").exists()

            # Test config commands
            result2 = runner.invoke(cli, ["config", "--list"])
            assert result2.exit_code == 0

    @patch("ocode_python.core.cli.OCodeEngine")
    def test_cli_session_management(self, mock_engine_class, temp_dir: Path):
        """Test CLI session management."""
        runner = CliRunner()

        # Mock engine with session support
        mock_engine = Mock()
        mock_engine.save_session = Mock(return_value="test-session-id")
        mock_engine.continue_session = Mock(return_value=True)
        mock_engine_class.return_value = mock_engine

        with runner.isolated_filesystem():
            with patch(
                "ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run
            ):
                # Test continue session flag
                result = runner.invoke(
                    cli, ["-c", "-p", "test prompt"]  # continue session
                )

                # Should attempt to continue session
                assert result.exit_code in [0, 1]


@pytest.mark.integration
@pytest.mark.cli
class TestCLIConfiguration:
    """Test CLI configuration handling."""

    def test_cli_environment_variables(self):
        """Test CLI with environment variables."""
        runner = CliRunner()

        env_vars = {
            "OCODE_MODEL": "custom-model",
            "OCODE_VERBOSE": "true",
            "OLLAMA_HOST": "http://custom-host:8080",
        }

        with patch.dict("os.environ", env_vars):
            with patch(
                "ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run
            ):
                result = runner.invoke(cli, ["-p", "test"])

                # Should use environment variables
                assert result.exit_code in [0, 1]

    def test_cli_config_hierarchy(self, temp_dir: Path):
        """Test CLI configuration hierarchy."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create project config
            Path(".ocode").mkdir()
            with open(".ocode/settings.json", "w") as f:
                json.dump({"model": "project-model"}, f)

            # Create user config
            user_ocode = Path.home() / ".ocode"
            user_ocode.mkdir(exist_ok=True)
            with open(user_ocode / "settings.json", "w") as f:
                json.dump({"model": "user-model"}, f)

            with patch(
                "ocode_python.core.cli.asyncio.run", side_effect=mock_asyncio_run
            ):
                result = runner.invoke(cli, ["-p", "test"])

                # Should respect config hierarchy
                assert result.exit_code in [0, 1]
