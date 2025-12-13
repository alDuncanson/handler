"""Authentication support for A2A protocol.

Handles credential storage and HTTP authentication header generation.
Currently supports API key and HTTP bearer authentication schemes.
"""

from dataclasses import dataclass
from enum import Enum


class AuthType(str, Enum):
    """Supported authentication types."""

    API_KEY = "api_key"
    BEARER = "bearer"


@dataclass
class AuthCredentials:
    """Authentication credentials for an agent.

    Stores the credential value and metadata about how to apply it.
    """

    auth_type: AuthType
    value: str
    header_name: str | None = None  # For API key: custom header name

    def to_headers(self) -> dict[str, str]:
        """Generate HTTP headers for this credential.

        Returns:
            Dictionary of headers to include in requests
        """
        if self.auth_type == AuthType.BEARER:
            return {"Authorization": f"Bearer {self.value}"}
        elif self.auth_type == AuthType.API_KEY:
            header = self.header_name or "X-API-Key"
            return {header: self.value}
        return {}

    def to_dict(self) -> dict[str, str | None]:
        """Serialize credentials for storage."""
        return {
            "auth_type": self.auth_type.value,
            "value": self.value,
            "header_name": self.header_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> "AuthCredentials":
        """Deserialize credentials from storage."""
        return cls(
            auth_type=AuthType(data["auth_type"]),
            value=data.get("value") or "",
            header_name=data.get("header_name"),
        )


def create_bearer_auth(token: str) -> AuthCredentials:
    """Create bearer token authentication."""
    return AuthCredentials(auth_type=AuthType.BEARER, value=token)


def create_api_key_auth(
    key: str,
    header_name: str = "X-API-Key",
) -> AuthCredentials:
    """Create API key authentication.

    Args:
        key: The API key value
        header_name: Header name to use (default: X-API-Key)
    """
    return AuthCredentials(
        auth_type=AuthType.API_KEY,
        value=key,
        header_name=header_name,
    )
