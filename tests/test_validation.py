"""Tests for A2A protocol validation."""

import json
import tempfile
from pathlib import Path

from a2a.types import AgentCard

from a2a_handler.validation import (
    ValidationSource,
    validate_agent_card_from_file,
)


def _minimal_valid_agent_card() -> dict:
    """Return a minimal valid agent card per A2A v0.3.0 spec.

    Required fields: name, description, url, version, capabilities,
    defaultInputModes, defaultOutputModes, skills (with id, name, tags).
    """
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "url": "http://localhost:8000",
        "version": "1.0.0",
        "capabilities": {},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "test_skill",
                "name": "Test Skill",
                "description": "A test skill",
                "tags": ["test"],
            }
        ],
    }


class TestAgentCardValidation:
    """Tests for agent card validation using the A2A SDK."""

    def test_valid_minimal_card(self):
        """Test validation of a minimal valid agent card."""
        data = _minimal_valid_agent_card()
        card = AgentCard.model_validate(data)

        assert card.name == "Test Agent"
        assert card.description == "A test agent"
        assert len(card.skills) == 1

    def test_missing_required_field(self):
        """Test validation fails when required field is missing."""
        data = {"url": "http://localhost:8000"}

        try:
            AgentCard.model_validate(data)
            assert False, "Expected validation to fail"
        except Exception:
            pass

    def test_skill_without_tags_fails_validation(self):
        """Test that skills without tags fail validation (tags are required in v0.3.0)."""
        data = _minimal_valid_agent_card()
        data["skills"] = [{"id": "test", "name": "Test", "description": "Test desc"}]

        try:
            AgentCard.model_validate(data)
            assert False, "Expected validation to fail"
        except Exception:
            pass


class TestValidateAgentCardFromFile:
    """Tests for validate_agent_card_from_file function."""

    def test_valid_file(self):
        """Test validation of a valid agent card file."""
        data = _minimal_valid_agent_card()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            result = validate_agent_card_from_file(f.name)

            assert result.valid is True
            assert result.source_type == ValidationSource.FILE
            assert result.agent_card is not None

            Path(f.name).unlink()

    def test_nonexistent_file(self):
        """Test validation fails for nonexistent file."""
        result = validate_agent_card_from_file("/nonexistent/path/agent.json")

        assert result.valid is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "file_error"

    def test_invalid_json_file(self):
        """Test validation fails for invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()

            result = validate_agent_card_from_file(f.name)

            assert result.valid is False
            assert len(result.issues) == 1
            assert result.issues[0].issue_type == "json_error"

            Path(f.name).unlink()

    def test_directory_path(self):
        """Test validation fails when path is a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_agent_card_from_file(tmpdir)

            assert result.valid is False
            assert len(result.issues) == 1
            assert result.issues[0].issue_type == "file_error"


class TestValidationResult:
    """Tests for ValidationResult properties."""

    def test_agent_name_from_card(self):
        """Test agent_name property returns name from agent card."""
        data = _minimal_valid_agent_card()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            result = validate_agent_card_from_file(f.name)
            assert result.agent_name == "Test Agent"

            Path(f.name).unlink()

    def test_agent_name_from_raw_data(self):
        """Test agent_name property returns name from raw data when card is None."""
        data = {"name": "Raw Agent", "url": "invalid"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            result = validate_agent_card_from_file(f.name)
            assert result.valid is False
            assert result.agent_name == "Raw Agent"

            Path(f.name).unlink()

    def test_protocol_version_from_sdk(self):
        """Test protocol_version returns the SDK default version."""
        data = _minimal_valid_agent_card()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            result = validate_agent_card_from_file(f.name)
            assert result.protocol_version is not None
            assert len(result.protocol_version) > 0

            Path(f.name).unlink()

    def test_protocol_version_explicit(self):
        """Test protocol_version returns explicit version when set."""
        data = _minimal_valid_agent_card()
        data["protocolVersion"] = "2.0"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()

            result = validate_agent_card_from_file(f.name)
            assert result.protocol_version == "2.0"

            Path(f.name).unlink()
