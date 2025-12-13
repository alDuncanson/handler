"""Tests for authentication module."""

from a2a_handler.auth import (
    AuthCredentials,
    AuthType,
    create_api_key_auth,
    create_bearer_auth,
)


class TestAuthCredentials:
    """Tests for AuthCredentials class."""

    def test_bearer_to_headers(self) -> None:
        """Bearer token generates Authorization header."""
        creds = AuthCredentials(auth_type=AuthType.BEARER, value="my-secret-token")
        headers = creds.to_headers()
        assert headers == {"Authorization": "Bearer my-secret-token"}

    def test_api_key_to_headers_default(self) -> None:
        """API key uses default X-API-Key header."""
        creds = AuthCredentials(auth_type=AuthType.API_KEY, value="my-api-key")
        headers = creds.to_headers()
        assert headers == {"X-API-Key": "my-api-key"}

    def test_api_key_to_headers_custom(self) -> None:
        """API key uses custom header name."""
        creds = AuthCredentials(
            auth_type=AuthType.API_KEY,
            value="my-api-key",
            header_name="X-Custom-Key",
        )
        headers = creds.to_headers()
        assert headers == {"X-Custom-Key": "my-api-key"}

    def test_to_dict_and_from_dict_bearer(self) -> None:
        """Bearer credentials round-trip through serialization."""
        original = AuthCredentials(auth_type=AuthType.BEARER, value="token123")
        data = original.to_dict()
        restored = AuthCredentials.from_dict(data)

        assert restored.auth_type == original.auth_type
        assert restored.value == original.value

    def test_to_dict_and_from_dict_api_key(self) -> None:
        """API key credentials round-trip through serialization."""
        original = AuthCredentials(
            auth_type=AuthType.API_KEY,
            value="key123",
            header_name="X-My-Key",
        )
        data = original.to_dict()
        restored = AuthCredentials.from_dict(data)

        assert restored.auth_type == original.auth_type
        assert restored.value == original.value
        assert restored.header_name == original.header_name


class TestAuthHelpers:
    """Tests for auth helper functions."""

    def test_create_bearer_auth(self) -> None:
        """create_bearer_auth creates correct credentials."""
        creds = create_bearer_auth("my-token")
        assert creds.auth_type == AuthType.BEARER
        assert creds.value == "my-token"

    def test_create_api_key_auth_default(self) -> None:
        """create_api_key_auth with defaults."""
        creds = create_api_key_auth("my-key")
        assert creds.auth_type == AuthType.API_KEY
        assert creds.value == "my-key"
        assert creds.header_name == "X-API-Key"

    def test_create_api_key_auth_custom(self) -> None:
        """create_api_key_auth with custom header."""
        creds = create_api_key_auth("my-key", header_name="Authorization")
        assert creds.header_name == "Authorization"
