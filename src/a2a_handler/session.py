"""Session state management for A2A CLI.

Provides persistence of context_id and task_id across CLI invocations.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from a2a_handler.common import get_logger

log = get_logger(__name__)

DEFAULT_SESSION_DIR = Path.home() / ".handler"
SESSION_FILE = "sessions.json"


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
    session_dir: Path = field(default_factory=lambda: DEFAULT_SESSION_DIR)

    @property
    def session_file(self) -> Path:
        """Path to the session file."""
        return self.session_dir / SESSION_FILE

    def _ensure_dir(self) -> None:
        """Ensure the session directory exists."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        """Load sessions from disk."""
        if not self.session_file.exists():
            log.debug("No session file found at %s", self.session_file)
            return

        try:
            with open(self.session_file) as f:
                data = json.load(f)

            for url, session_data in data.items():
                self.sessions[url] = AgentSession(
                    agent_url=url,
                    context_id=session_data.get("context_id"),
                    task_id=session_data.get("task_id"),
                )
            log.debug(
                "Loaded %d sessions from %s", len(self.sessions), self.session_file
            )

        except json.JSONDecodeError as e:
            log.warning("Failed to parse session file: %s", e)
        except OSError as e:
            log.warning("Failed to read session file: %s", e)

    def save(self) -> None:
        """Save sessions to disk."""
        self._ensure_dir()

        data: dict[str, Any] = {}
        for url, session in self.sessions.items():
            data[url] = {
                "context_id": session.context_id,
                "task_id": session.task_id,
            }

        try:
            with open(self.session_file, "w") as f:
                json.dump(data, f, indent=2)
            log.debug("Saved %d sessions to %s", len(self.sessions), self.session_file)
        except OSError as e:
            log.warning("Failed to write session file: %s", e)

    def get(self, agent_url: str) -> AgentSession:
        """Get or create a session for an agent URL."""
        if agent_url not in self.sessions:
            self.sessions[agent_url] = AgentSession(agent_url=agent_url)
        return self.sessions[agent_url]

    def update(
        self,
        agent_url: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> AgentSession:
        """Update session for an agent and save."""
        session = self.get(agent_url)
        session.update(context_id, task_id)
        self.save()
        return session

    def clear(self, agent_url: str | None = None) -> None:
        """Clear session(s).

        Args:
            agent_url: If provided, clear only that agent's session.
                      Otherwise, clear all sessions.
        """
        if agent_url:
            if agent_url in self.sessions:
                del self.sessions[agent_url]
                log.info("Cleared session for %s", agent_url)
        else:
            self.sessions.clear()
            log.info("Cleared all sessions")
        self.save()

    def list_all(self) -> list[AgentSession]:
        """List all sessions."""
        return list(self.sessions.values())


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store (singleton)."""
    global _store
    if _store is None:
        _store = SessionStore()
        _store.load()
    return _store


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
