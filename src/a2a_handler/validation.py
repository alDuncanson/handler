"""A2A protocol validation utilities."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from a2a.types import AgentCard
from pydantic import ValidationError

from a2a_handler.common import get_logger

log = get_logger(__name__)


class ValidationSource(Enum):
    """Source type for agent card validation."""

    URL = "url"
    FILE = "file"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""

    field: str
    message: str
    issue_type: str = "error"

    def __str__(self) -> str:
        return f"[{self.issue_type}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validating an agent card."""

    valid: bool
    source: str
    source_type: ValidationSource
    agent_card: AgentCard | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    raw_data: dict[str, Any] | None = None

    @property
    def agent_name(self) -> str:
        """Get the agent name if available."""
        if self.agent_card:
            return self.agent_card.name
        if self.raw_data:
            return self.raw_data.get("name", "Unknown")
        return "Unknown"

    @property
    def protocol_version(self) -> str:
        """Get the protocol version if available."""
        if self.agent_card:
            return self.agent_card.protocol_version or "1.0"
        if self.raw_data:
            return self.raw_data.get("protocolVersion", "1.0")
        return "Unknown"


def _parse_pydantic_error(error: ValidationError) -> list[ValidationIssue]:
    """Parse Pydantic validation errors into ValidationIssues."""
    issues = []
    for err in error.errors():
        field_path = ".".join(str(loc) for loc in err["loc"])
        message = err["msg"]
        issue_type = err["type"]
        issues.append(
            ValidationIssue(
                field=field_path or "root",
                message=message,
                issue_type=issue_type,
            )
        )
    return issues


def _check_best_practices(card: AgentCard) -> list[ValidationIssue]:
    """Check for best practices and generate warnings.

    Note: In A2A v0.3.0, the following are REQUIRED fields and validated by Pydantic:
    - name, description, url, version
    - capabilities, defaultInputModes, defaultOutputModes, skills
    - preferredTransport (defaults to JSONRPC in SDK)

    This function only warns about optional fields that improve agent discoverability.
    """
    warnings = []

    if not card.provider:
        warnings.append(
            ValidationIssue(
                field="provider",
                message="Agent card should specify a provider for better discoverability",
                issue_type="warning",
            )
        )

    if not card.documentation_url:
        warnings.append(
            ValidationIssue(
                field="documentationUrl",
                message="Agent card should include documentation URL",
                issue_type="warning",
            )
        )

    if not card.icon_url:
        warnings.append(
            ValidationIssue(
                field="iconUrl",
                message="Agent card should include an icon URL for UI display",
                issue_type="warning",
            )
        )

    if card.skills:
        for i, skill in enumerate(card.skills):
            if not skill.description:
                warnings.append(
                    ValidationIssue(
                        field=f"skills[{i}].description",
                        message=f"Skill '{skill.name}' should have a description",
                        issue_type="warning",
                    )
                )
            if not skill.examples or len(skill.examples) == 0:
                warnings.append(
                    ValidationIssue(
                        field=f"skills[{i}].examples",
                        message=f"Skill '{skill.name}' should include example prompts",
                        issue_type="warning",
                    )
                )

    if not card.additional_interfaces or len(card.additional_interfaces) == 0:
        warnings.append(
            ValidationIssue(
                field="additionalInterfaces",
                message="Consider declaring additional transport interfaces for flexibility",
                issue_type="warning",
            )
        )

    return warnings


def validate_agent_card_data(
    data: dict[str, Any], source: str, source_type: ValidationSource
) -> ValidationResult:
    """Validate agent card data against the A2A protocol schema.

    Args:
        data: Raw agent card data as a dictionary
        source: The source (URL or file path) of the data
        source_type: Whether the source is a URL or file

    Returns:
        ValidationResult with validation status and any issues
    """
    log.debug("Validating agent card data from %s", source)

    try:
        card = AgentCard.model_validate(data)
        log.info("Agent card validation successful for %s", card.name)

        warnings = _check_best_practices(card)

        return ValidationResult(
            valid=True,
            source=source,
            source_type=source_type,
            agent_card=card,
            warnings=warnings,
            raw_data=data,
        )

    except ValidationError as e:
        log.warning("Agent card validation failed: %s", e)
        issues = _parse_pydantic_error(e)

        return ValidationResult(
            valid=False,
            source=source,
            source_type=source_type,
            issues=issues,
            raw_data=data,
        )


async def validate_agent_card_from_url(
    url: str,
    client: httpx.AsyncClient | None = None,
    card_path: str | None = None,
) -> ValidationResult:
    """Fetch and validate an agent card from a URL.

    Args:
        url: The base URL of the agent
        client: Optional HTTP client to use
        card_path: Optional custom path to the agent card (default: /.well-known/agent.json)

    Returns:
        ValidationResult with validation status and any issues
    """
    log.info("Validating agent card from URL: %s", url)

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=30)

    try:
        base_url = url.rstrip("/")
        if card_path:
            full_url = f"{base_url}/{card_path.lstrip('/')}"
        else:
            full_url = f"{base_url}/.well-known/agent-card.json"

        log.debug("Fetching agent card from %s", full_url)
        response = await client.get(full_url)
        response.raise_for_status()

        data = response.json()
        return validate_agent_card_data(data, url, ValidationSource.URL)

    except httpx.HTTPStatusError as e:
        log.error("HTTP error fetching agent card: %s", e)
        return ValidationResult(
            valid=False,
            source=url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field="http",
                    message=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                    issue_type="http_error",
                )
            ],
        )

    except httpx.RequestError as e:
        log.error("Request error fetching agent card: %s", e)
        return ValidationResult(
            valid=False,
            source=url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field="connection",
                    message=str(e),
                    issue_type="connection_error",
                )
            ],
        )

    except json.JSONDecodeError as e:
        log.error("JSON decode error: %s", e)
        return ValidationResult(
            valid=False,
            source=url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field="json",
                    message=f"Invalid JSON: {e}",
                    issue_type="json_error",
                )
            ],
        )

    finally:
        if should_close:
            await client.aclose()


def validate_agent_card_from_file(file_path: str | Path) -> ValidationResult:
    """Validate an agent card from a local file.

    Args:
        file_path: Path to the agent card JSON file

    Returns:
        ValidationResult with validation status and any issues
    """
    path = Path(file_path)
    log.info("Validating agent card from file: %s", path)

    if not path.exists():
        log.error("File not found: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field="file",
                    message=f"File not found: {path}",
                    issue_type="file_error",
                )
            ],
        )

    if not path.is_file():
        log.error("Path is not a file: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field="file",
                    message=f"Path is not a file: {path}",
                    issue_type="file_error",
                )
            ],
        )

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return validate_agent_card_data(data, str(path), ValidationSource.FILE)

    except json.JSONDecodeError as e:
        log.error("JSON decode error: %s", e)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field="json",
                    message=f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}",
                    issue_type="json_error",
                )
            ],
        )

    except PermissionError:
        log.error("Permission denied reading file: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field="file",
                    message=f"Permission denied: {path}",
                    issue_type="file_error",
                )
            ],
        )

    except OSError as e:
        log.error("Error reading file: %s", e)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field="file",
                    message=str(e),
                    issue_type="file_error",
                )
            ],
        )
