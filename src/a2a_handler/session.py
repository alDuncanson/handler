"""Session state management for the Handler CLI.

Persists context_id and task_id across CLI invocations for conversation continuity.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from a2a_handler.common import get_logger

logger = get_logger(__name__)

DEFAULT_SESSION_DIRECTORY = Path.home() / ".handler"
SESSION_FILENAME = "sessions.json"


@dataclass
class AgentSession:
    """Session state for a single agent."""

    agent_url: str
    context_id: str | None = None
    task_id: str | None = None

    def update(
        self,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Update session with new values (only if provided)."""
        if context_id is not None:
            self.context_id = context_id
        if task_id is not None:
            self.task_id = task_id


@dataclass
class SessionStore:
    """Persistent store for agent sessions."""

    sessions: dict[str, AgentSession] = field(default_factory=dict)
    session_directory: Path = field(default_factory=lambda: DEFAULT_SESSION_DIRECTORY)

    @property
    def session_file_path(self) -> Path:
        """Path to the session file."""
        return self.session_directory / SESSION_FILENAME

    def _ensure_directory_exists(self) -> None:
        """Ensure the session directory exists."""
        self.session_directory.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        """Load sessions from disk."""
        if not self.session_file_path.exists():
            logger.debug("No session file found at %s", self.session_file_path)
            return

        try:
            with open(self.session_file_path) as session_file:
                session_data = json.load(session_file)

            for agent_url, agent_session_data in session_data.items():
                self.sessions[agent_url] = AgentSession(
                    agent_url=agent_url,
                    context_id=agent_session_data.get("context_id"),
                    task_id=agent_session_data.get("task_id"),
                )

            logger.debug(
                "Loaded %d sessions from %s",
                len(self.sessions),
                self.session_file_path,
            )

        except json.JSONDecodeError as error:
            logger.warning("Failed to parse session file: %s", error)
        except OSError as error:
            logger.warning("Failed to read session file: %s", error)

    def save(self) -> None:
        """Save sessions to disk."""
        self._ensure_directory_exists()

        session_data: dict[str, Any] = {}
        for agent_url, agent_session in self.sessions.items():
            session_data[agent_url] = {
                "context_id": agent_session.context_id,
                "task_id": agent_session.task_id,
            }

        try:
            with open(self.session_file_path, "w") as session_file:
                json.dump(session_data, session_file, indent=2)
            logger.debug(
                "Saved %d sessions to %s",
                len(self.sessions),
                self.session_file_path,
            )
        except OSError as error:
            logger.warning("Failed to write session file: %s", error)

    def get(self, agent_url: str) -> AgentSession:
        """Get or create a session for an agent URL."""
        if agent_url not in self.sessions:
            self.sessions[agent_url] = AgentSession(agent_url=agent_url)
            logger.debug("Created new session for %s", agent_url)
        return self.sessions[agent_url]

    def update(
        self,
        agent_url: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> AgentSession:
        """Update session for an agent and save."""
        agent_session = self.get(agent_url)
        agent_session.update(context_id, task_id)
        self.save()
        logger.debug(
            "Updated session for %s: context_id=%s, task_id=%s",
            agent_url,
            context_id,
            task_id,
        )
        return agent_session

    def clear(self, agent_url: str | None = None) -> None:
        """Clear session(s).

        Args:
            agent_url: If provided, clear only that agent's session.
                      Otherwise, clear all sessions.
        """
        if agent_url:
            if agent_url in self.sessions:
                del self.sessions[agent_url]
                logger.info("Cleared session for %s", agent_url)
        else:
            session_count = len(self.sessions)
            self.sessions.clear()
            logger.info("Cleared all %d sessions", session_count)
        self.save()

    def list_all(self) -> list[AgentSession]:
        """List all sessions."""
        return list(self.sessions.values())


_global_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store (singleton)."""
    global _global_session_store
    if _global_session_store is None:
        _global_session_store = SessionStore()
        _global_session_store.load()
        logger.debug("Initialized global session store")
    return _global_session_store


def get_session(agent_url: str) -> AgentSession:
    """Get session for an agent URL."""
    return get_session_store().get(agent_url)


def update_session(
    agent_url: str,
    context_id: str | None = None,
    task_id: str | None = None,
) -> AgentSession:
    """Update and persist session for an agent."""
    return get_session_store().update(agent_url, context_id, task_id)


def clear_session(agent_url: str | None = None) -> None:
    """Clear session(s)."""
    get_session_store().clear(agent_url)
