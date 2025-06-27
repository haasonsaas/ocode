"""Comprehensive unit tests for authentication system."""

import json
import tempfile
from pathlib import Path

import pytest

from ocode_python.utils.auth import AuthenticationManager


class TestAuthenticationManager:
    """Test AuthenticationManager class."""

    @pytest.fixture
    def temp_home(self):
        """Create temporary home directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def auth_manager(self, temp_home):
        """Create AuthenticationManager with temp directory."""
        return AuthenticationManager(auth_dir=temp_home / ".ocode")

    def test_init(self, auth_manager, temp_home):
        """Test AuthenticationManager initialization."""
        expected_path = temp_home / ".ocode" / "auth.json"
        assert auth_manager.auth_file == expected_path
        assert auth_manager.auth_file.parent.exists()

    def test_load_auth_no_file(self, auth_manager):
        """Test loading auth when file doesn't exist."""
        result = auth_manager._load_auth_file()
        assert result == {}

    def test_load_auth_with_file(self, auth_manager, temp_home):
        """Test loading auth from file."""
        auth_data = {"api_key": "test-key", "username": "testuser"}
        auth_file = temp_home / ".ocode" / "auth.json"
        auth_file.write_text(json.dumps(auth_data))

        result = auth_manager._load_auth_file()
        assert result == auth_data

    def test_load_auth_invalid_json(self, auth_manager, temp_home):
        """Test loading invalid JSON auth file."""
        auth_file = temp_home / ".ocode" / "auth.json"
        auth_file.write_text("invalid json")

        result = auth_manager._load_auth_file()
        assert result == {}

    def test_save_auth(self, auth_manager, temp_home):
        """Test saving auth data."""
        auth_data = {"api_key": "test-key", "username": "testuser"}
        success = auth_manager._save_auth_file(auth_data)
        assert success

        auth_file = temp_home / ".ocode" / "auth.json"
        assert auth_file.exists()

        loaded_data = json.loads(auth_file.read_text())
        assert loaded_data == auth_data

    def test_get_api_key(self, auth_manager):
        """Test getting API key."""
        auth_manager.save_api_key("test-key")
        assert auth_manager.get_api_key() == "test-key"

    def test_get_api_key_missing(self, auth_manager):
        """Test getting API key when not set."""
        assert auth_manager.get_api_key() is None

    def test_save_api_key(self, auth_manager):
        """Test saving API key."""
        success = auth_manager.save_api_key("new-key")
        assert success
        assert auth_manager.get_api_key() == "new-key"

    def test_logout(self, auth_manager, temp_home):
        """Test clearing auth data."""
        auth_manager.save_api_key("test-key")
        auth_file = temp_home / ".ocode" / "auth.json"
        assert auth_file.exists()

        success = auth_manager.logout()
        assert success
        assert not auth_file.exists()

    def test_logout_no_file(self, auth_manager):
        """Test logout when file doesn't exist."""
        success = auth_manager.logout()
        assert success

    def test_is_authenticated_with_api_key(self, auth_manager):
        """Test authentication check with API key."""
        auth_manager.save_api_key("test-key")
        # Note: is_authenticated checks for tokens, not API keys in this implementation
        # So we test token functionality
        auth_manager.save_token("test-token")
        assert auth_manager.is_authenticated()

    def test_is_authenticated_no_auth(self, auth_manager):
        """Test authentication check without auth."""
        assert not auth_manager.is_authenticated()


class TestAuthToken:
    """Test AuthToken functionality."""

    def test_auth_token_creation(self):
        """Test creating auth tokens."""
        from ocode_python.utils.auth import AuthToken

        token = AuthToken("test-token", expires_at=1234567890)
        assert token.token == "test-token"
        assert token.expires_at == 1234567890
        assert token.token_type == "Bearer"
        assert token.scope is None

    def test_auth_token_expiration(self):
        """Test token expiration check."""
        import time

        from ocode_python.utils.auth import AuthToken

        # Non-expiring token
        token1 = AuthToken("test-token")
        assert not token1.is_expired()

        # Expired token
        token2 = AuthToken("test-token", expires_at=time.time() - 3600)
        assert token2.is_expired()

        # Future token
        token3 = AuthToken("test-token", expires_at=time.time() + 3600)
        assert not token3.is_expired()

    def test_auth_token_serialization(self):
        """Test token serialization."""
        from ocode_python.utils.auth import AuthToken

        token = AuthToken("test-token", expires_at=1234567890, scope="read")
        data = token.to_dict()

        assert data["token"] == "test-token"
        assert data["expires_at"] == 1234567890
        assert data["scope"] == "read"

        # Test deserialization
        token2 = AuthToken.from_dict(data)
        assert token2.token == token.token
        assert token2.expires_at == token.expires_at
        assert token2.scope == token.scope
