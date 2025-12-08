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

logger = get_logger(__name__)


class ValidationSource(Enum):
    """Source type for agent card validation."""

    URL = "url"
    FILE = "file"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""

    field_name: str
    message: str
    issue_type: str = "error"

    def __str__(self) -> str:
        return f"[{self.issue_type}] {self.field_name}: {self.message}"


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


def parse_pydantic_validation_errors(
    validation_error: ValidationError,
) -> list[ValidationIssue]:
    """Parse Pydantic validation errors into ValidationIssues."""
    validation_issues = []
    for error_detail in validation_error.errors():
        field_path = ".".join(str(location) for location in error_detail["loc"])
        error_message = error_detail["msg"]
        error_type = error_detail["type"]
        validation_issues.append(
            ValidationIssue(
                field_name=field_path or "root",
                message=error_message,
                issue_type=error_type,
            )
        )
    return validation_issues


def check_agent_card_best_practices(agent_card: AgentCard) -> list[ValidationIssue]:
    """Check for best practices and generate warnings.

    Note: In A2A v0.3.0, the following are REQUIRED fields and validated by Pydantic:
    - name, description, url, version
    - capabilities, defaultInputModes, defaultOutputModes, skills
    - preferredTransport (defaults to JSONRPC in SDK)

    This function only warns about optional fields that improve agent discoverability.
    """
    best_practice_warnings = []

    if not agent_card.provider:
        best_practice_warnings.append(
            ValidationIssue(
                field_name="provider",
                message="Agent card should specify a provider for better discoverability",
                issue_type="warning",
            )
        )

    if not agent_card.documentation_url:
        best_practice_warnings.append(
            ValidationIssue(
                field_name="documentationUrl",
                message="Agent card should include documentation URL",
                issue_type="warning",
            )
        )

    if not agent_card.icon_url:
        best_practice_warnings.append(
            ValidationIssue(
                field_name="iconUrl",
                message="Agent card should include an icon URL for UI display",
                issue_type="warning",
            )
        )

    if agent_card.skills:
        for skill_index, skill in enumerate(agent_card.skills):
            if not skill.description:
                best_practice_warnings.append(
                    ValidationIssue(
                        field_name=f"skills[{skill_index}].description",
                        message=f"Skill '{skill.name}' should have a description",
                        issue_type="warning",
                    )
                )
            if not skill.examples or len(skill.examples) == 0:
                best_practice_warnings.append(
                    ValidationIssue(
                        field_name=f"skills[{skill_index}].examples",
                        message=f"Skill '{skill.name}' should include example prompts",
                        issue_type="warning",
                    )
                )

    if (
        not agent_card.additional_interfaces
        or len(agent_card.additional_interfaces) == 0
    ):
        best_practice_warnings.append(
            ValidationIssue(
                field_name="additionalInterfaces",
                message="Consider declaring additional transport interfaces for flexibility",
                issue_type="warning",
            )
        )

    return best_practice_warnings


def validate_agent_card_data(
    card_data: dict[str, Any],
    source: str,
    source_type: ValidationSource,
) -> ValidationResult:
    """Validate agent card data against the A2A protocol schema.

    Args:
        card_data: Raw agent card data as a dictionary
        source: The source (URL or file path) of the data
        source_type: Whether the source is a URL or file

    Returns:
        ValidationResult with validation status and any issues
    """
    logger.debug("Validating agent card data from %s", source)

    try:
        agent_card = AgentCard.model_validate(card_data)
        logger.info("Agent card validation successful for %s", agent_card.name)

        best_practice_warnings = check_agent_card_best_practices(agent_card)

        return ValidationResult(
            valid=True,
            source=source,
            source_type=source_type,
            agent_card=agent_card,
            warnings=best_practice_warnings,
            raw_data=card_data,
        )

    except ValidationError as validation_error:
        logger.warning("Agent card validation failed: %s", validation_error)
        validation_issues = parse_pydantic_validation_errors(validation_error)

        return ValidationResult(
            valid=False,
            source=source,
            source_type=source_type,
            issues=validation_issues,
            raw_data=card_data,
        )


async def validate_agent_card_from_url(
    agent_url: str,
    http_client: httpx.AsyncClient | None = None,
    agent_card_path: str | None = None,
) -> ValidationResult:
    """Fetch and validate an agent card from a URL.

    Args:
        agent_url: The base URL of the agent
        http_client: Optional HTTP client to use
        agent_card_path: Optional custom path to the agent card (default: /.well-known/agent.json)

    Returns:
        ValidationResult with validation status and any issues
    """
    logger.info("Validating agent card from URL: %s", agent_url)

    should_close_client = http_client is None
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=30)

    try:
        base_url = agent_url.rstrip("/")
        if agent_card_path:
            full_url = f"{base_url}/{agent_card_path.lstrip('/')}"
        else:
            full_url = f"{base_url}/.well-known/agent-card.json"

        logger.debug("Fetching agent card from %s", full_url)
        response = await http_client.get(full_url)
        response.raise_for_status()

        card_data = response.json()
        return validate_agent_card_data(card_data, agent_url, ValidationSource.URL)

    except httpx.HTTPStatusError as http_error:
        logger.error("HTTP error fetching agent card: %s", http_error)
        return ValidationResult(
            valid=False,
            source=agent_url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field_name="http",
                    message=f"HTTP {http_error.response.status_code}: {http_error.response.text[:200]}",
                    issue_type="http_error",
                )
            ],
        )

    except httpx.RequestError as request_error:
        logger.error("Request error fetching agent card: %s", request_error)
        return ValidationResult(
            valid=False,
            source=agent_url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field_name="connection",
                    message=str(request_error),
                    issue_type="connection_error",
                )
            ],
        )

    except json.JSONDecodeError as json_error:
        logger.error("JSON decode error: %s", json_error)
        return ValidationResult(
            valid=False,
            source=agent_url,
            source_type=ValidationSource.URL,
            issues=[
                ValidationIssue(
                    field_name="json",
                    message=f"Invalid JSON: {json_error}",
                    issue_type="json_error",
                )
            ],
        )

    finally:
        if should_close_client:
            await http_client.aclose()


def validate_agent_card_from_file(file_path: str | Path) -> ValidationResult:
    """Validate an agent card from a local file.

    Args:
        file_path: Path to the agent card JSON file

    Returns:
        ValidationResult with validation status and any issues
    """
    path = Path(file_path)
    logger.info("Validating agent card from file: %s", path)

    if not path.exists():
        logger.error("File not found: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field_name="file",
                    message=f"File not found: {path}",
                    issue_type="file_error",
                )
            ],
        )

    if not path.is_file():
        logger.error("Path is not a file: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field_name="file",
                    message=f"Path is not a file: {path}",
                    issue_type="file_error",
                )
            ],
        )

    try:
        with open(path, encoding="utf-8") as card_file:
            card_data = json.load(card_file)

        return validate_agent_card_data(card_data, str(path), ValidationSource.FILE)

    except json.JSONDecodeError as json_error:
        logger.error("JSON decode error: %s", json_error)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field_name="json",
                    message=f"Invalid JSON at line {json_error.lineno}, column {json_error.colno}: {json_error.msg}",
                    issue_type="json_error",
                )
            ],
        )

    except PermissionError:
        logger.error("Permission denied reading file: %s", path)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field_name="file",
                    message=f"Permission denied: {path}",
                    issue_type="file_error",
                )
            ],
        )

    except OSError as os_error:
        logger.error("Error reading file: %s", os_error)
        return ValidationResult(
            valid=False,
            source=str(path),
            source_type=ValidationSource.FILE,
            issues=[
                ValidationIssue(
                    field_name="file",
                    message=str(os_error),
                    issue_type="file_error",
                )
            ],
        )
