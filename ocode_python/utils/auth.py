"""
Authentication management for OCode.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    # Fallback for environments where requests is not available
    requests = None  # type: ignore
    REQUESTS_AVAILABLE = False


@dataclass
class AuthToken:
    """Authentication token information."""

    token: str
    expires_at: Optional[float] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if token is expired.

        Returns:
            True if token has an expiry time and it has passed.
        """
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the token.
        """
        return {
            "token": self.token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthToken":
        """Create from dictionary.

        Args:
            data: Dictionary containing token data.

        Returns:
            AuthToken instance.
        """
        return cls(
            token=data["token"],
            expires_at=data.get("expires_at"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )


class AuthenticationManager:
    """
    Manages authentication for OCode.

    Handles API keys, tokens, and authentication state.
    """

    def __init__(self, auth_dir: Optional[Path] = None):
        """
        Initialize authentication manager.

        Args:
            auth_dir: Directory to store authentication files
        """
        self.auth_dir = auth_dir or Path.home() / ".ocode"
        self.auth_dir.mkdir(parents=True, exist_ok=True)

        self.auth_file = self.auth_dir / "auth.json"
        self._cached_token: Optional[AuthToken] = None

    def _load_auth_file(self) -> Dict[str, Any]:
        """Load authentication data from file.

        Returns:
            Dictionary of authentication data, empty dict if file doesn't exist
            or contains invalid data.
        """
        if not self.auth_file.exists():
            return {}

        try:
            with open(self.auth_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to load auth file: {e}")
            return {}

    def _save_auth_file(self, data: Dict[str, Any]) -> bool:
        """Save authentication data to file.

        Sets restrictive file permissions (0o600) for security.

        Args:
            data: Authentication data to save.

        Returns:
            True if saved successfully, False on error.
        """
        try:
            with open(self.auth_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Set restrictive permissions
            self.auth_file.chmod(0o600)
            return True

        except OSError as e:
            print(f"Failed to save auth file: {e}")
            return False

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated.

        Returns:
            True if a valid, non-expired token exists.
        """
        token = self.get_token()
        return token is not None and not token.is_expired()

    def get_token(self) -> Optional[AuthToken]:
        """Get current authentication token.

        Uses caching to avoid repeated file reads. Returns None
        if no token exists or token is expired.

        Returns:
            AuthToken if valid token exists, None otherwise.
        """
        if self._cached_token and not self._cached_token.is_expired():
            return self._cached_token

        # Load from file
        auth_data = self._load_auth_file()
        token_data = auth_data.get("token")

        if not token_data:
            return None

        try:
            token = AuthToken.from_dict(token_data)
            if not token.is_expired():
                self._cached_token = token
                return token
        except Exception as e:
            print(f"Invalid token data: {e}")

        return None

    def token(self) -> Optional[str]:
        """Get current token string.

        Convenience method to get just the token string.

        Returns:
            Token string if authenticated, None otherwise.
        """
        auth_token = self.get_token()
        return auth_token.token if auth_token else None

    def save_token(
        self,
        token: str,
        expires_at: Optional[float] = None,
        token_type: str = "Bearer",  # nosec B107 - Standard OAuth token type, not a password  # noqa: E501
        scope: Optional[str] = None,
    ) -> bool:
        """
        Save authentication token.

        Args:
            token: Token string
            expires_at: Token expiration timestamp
            token_type: Token type (e.g., "Bearer")
            scope: Token scope

        Returns:
            True if saved successfully
        """
        auth_token = AuthToken(
            token=token, expires_at=expires_at, token_type=token_type, scope=scope
        )

        auth_data = self._load_auth_file()
        auth_data["token"] = auth_token.to_dict()

        if self._save_auth_file(auth_data):
            self._cached_token = auth_token
            return True

        return False

    def save_api_key(self, api_key: str) -> bool:
        """
        Save API key for long-term authentication.

        Args:
            api_key: API key string

        Returns:
            True if saved successfully
        """
        auth_data = self._load_auth_file()
        auth_data["api_key"] = api_key

        return self._save_auth_file(auth_data)

    def get_api_key(self) -> Optional[str]:
        """Get saved API key.

        Returns:
            API key string if saved, None otherwise.
        """
        auth_data = self._load_auth_file()
        return auth_data.get("api_key")

    def logout(self) -> bool:
        """
        Clear authentication data.

        Returns:
            True if cleared successfully
        """
        try:
            if self.auth_file.exists():
                self.auth_file.unlink()

            self._cached_token = None
            return True

        except OSError:
            return False

    def refresh_token(self) -> bool:
        """
        Refresh authentication token if possible.

        Returns:
            True if refreshed successfully
        """
        if not REQUESTS_AVAILABLE:
            return False

        # Get stored credentials
        credentials = self.get_credentials()
        refresh_token = credentials.get("refresh_token")

        if not refresh_token:
            return False

        try:
            # Make request to refresh token endpoint
            # Get token endpoint from credentials or use default
            token_endpoint = credentials.get(
                "token_endpoint", "https://auth.ocode.com/oauth/token"
            )

            # Prepare refresh token request
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": credentials.get("client_id"),
            }

            # Add client secret if available
            if "client_secret" in credentials:
                data["client_secret"] = credentials["client_secret"]

            # Make the request
            response = requests.post(token_endpoint, data=data, timeout=30)
            response.raise_for_status()

            # Parse response
            token_data = response.json()

            # Save new tokens
            success = self.save_token(
                token=token_data["access_token"],
                expires_at=time.time() + token_data.get("expires_in", 3600),
                token_type=token_data.get("token_type", "Bearer"),
                scope=token_data.get("scope"),
            )

            # Save new refresh token if provided
            if "refresh_token" in token_data:
                credentials["refresh_token"] = token_data["refresh_token"]
                self.save_credentials(credentials)

            return success

        except Exception as e:
            print(f"Failed to refresh token: {e}")
            return False

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.

        Returns:
            Dictionary of headers
        """
        headers = {}

        token = self.get_token()
        if token:
            headers["Authorization"] = f"{token.token_type} {token.token}"
        else:
            # Try API key as fallback
            api_key = self.get_api_key()
            if api_key:
                headers["X-API-Key"] = api_key

        return headers

    def save_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Save additional credentials.

        Args:
            credentials: Dictionary of credential data

        Returns:
            True if saved successfully
        """
        auth_data = self._load_auth_file()
        auth_data["credentials"] = credentials

        return self._save_auth_file(auth_data)

    def get_credentials(self) -> Dict[str, Any]:
        """Get saved credentials.

        Returns:
            Dictionary of saved credentials, empty dict if none exist.
        """
        auth_data = self._load_auth_file()
        credentials = auth_data.get("credentials", {})
        return credentials if isinstance(credentials, dict) else {}

    def get_auth_status(self) -> Dict[str, Any]:
        """
        Get current authentication status.

        Returns:
            Status information
        """
        token = self.get_token()
        api_key = self.get_api_key()

        status = {
            "authenticated": self.is_authenticated(),
            "has_token": token is not None,
            "has_api_key": api_key is not None,
            "token_expired": token.is_expired() if token else None,
            "token_expires_at": token.expires_at if token else None,
            "auth_file_exists": self.auth_file.exists(),
        }

        return status


class OIDCAuthenticator:
    """
    OIDC (OpenID Connect) authentication for enterprise environments.
    """

    def __init__(
        self,
        auth_manager: AuthenticationManager,
        issuer_url: str,
        client_id: str,
        client_secret: Optional[str] = None,
    ):
        """
        Initialize OIDC authenticator.

        Args:
            auth_manager: Authentication manager instance
            issuer_url: OIDC issuer URL
            client_id: OIDC client ID
            client_secret: OIDC client secret (for confidential clients)
        """
        self.auth_manager = auth_manager
        self.issuer_url = issuer_url
        self.client_id = client_id
        self.client_secret = client_secret

    async def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate using OIDC Resource Owner Password Credentials flow.

        Args:
            username: Username
            password: Password

        Returns:
            True if authentication successful
        """
        try:
            import aiohttp

            # Discover OIDC endpoints
            async with aiohttp.ClientSession() as session:
                # Get OIDC configuration
                async with session.get(
                    f"{self.issuer_url}/.well-known/openid-configuration"
                ) as response:
                    if response.status != 200:
                        return False
                    config = await response.json()

                # Get token endpoint
                token_endpoint = config.get("token_endpoint")
                if not token_endpoint:
                    return False

                # Prepare token request
                data = {
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                    "client_id": self.client_id,
                    "scope": "openid profile email",
                }

                # Add client secret if available
                if self.client_secret:
                    data["client_secret"] = self.client_secret

                # Make token request
                async with session.post(token_endpoint, data=data) as response:
                    if response.status != 200:
                        return False

                    token_data = await response.json()

                    # Save tokens
                    success = self.auth_manager.save_token(
                        token=token_data["access_token"],
                        expires_at=time.time() + token_data.get("expires_in", 3600),
                        token_type=token_data.get("token_type", "Bearer"),
                        scope=token_data.get("scope"),
                    )

                    # Save refresh token and other credentials
                    credentials = {
                        "refresh_token": token_data.get("refresh_token"),
                        "token_endpoint": token_endpoint,
                        "client_id": self.client_id,
                    }
                    if self.client_secret:
                        credentials["client_secret"] = self.client_secret

                    self.auth_manager.save_credentials(credentials)

                    return success

        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    async def device_flow_authenticate(self) -> bool:
        """
        Authenticate using OIDC Device Authorization flow.

        Returns:
            True if authentication successful
        """
        # Placeholder for device flow
        # Would implement full device authorization flow here
        return False


def main() -> None:
    """Example usage of AuthenticationManager.

    Demonstrates basic authentication operations including
    status checking, API key management, and header generation.
    """
    auth = AuthenticationManager()

    print("Authentication Status:")
    status = auth.get_auth_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # Save a test API key
    print("\nSaving test API key...")
    auth.save_api_key("test-api-key-12345")

    # Check status again
    print("\nUpdated Status:")
    status = auth.get_auth_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # Get auth headers
    headers = auth.get_auth_headers()
    print(f"\nAuth headers: {headers}")


if __name__ == "__main__":
    main()
