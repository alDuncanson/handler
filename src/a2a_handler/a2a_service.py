"""A2A protocol service layer.

Provides a unified interface for A2A operations, reusable between CLI and TUI.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    GetTaskPushNotificationConfigParams,
    Message,
    Part,
    PushNotificationConfig,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
    TransportProtocol,
)

from a2a_handler.common import get_logger

log = get_logger(__name__)

TERMINAL_STATES = {
    TaskState.completed,
    TaskState.canceled,
    TaskState.failed,
    TaskState.rejected,
}


@dataclass
class SendResult:
    """Result from sending a message to an agent."""

    task: Task | None = None
    message: Message | None = None
    context_id: str | None = None
    task_id: str | None = None
    state: TaskState | None = None
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Check if the task reached a terminal state."""
        return self.state in TERMINAL_STATES if self.state else False

    @property
    def needs_input(self) -> bool:
        """Check if the task is waiting for user input."""
        return self.state == TaskState.input_required if self.state else False


@dataclass
class StreamEvent:
    """A single event from a streaming response."""

    event_type: str  # "task", "message", "status", "artifact"
    task: Task | None = None
    message: Message | None = None
    status: TaskStatusUpdateEvent | None = None
    artifact: TaskArtifactUpdateEvent | None = None
    context_id: str | None = None
    task_id: str | None = None
    state: TaskState | None = None
    text: str = ""


@dataclass
class TaskResult:
    """Result from a task operation (get/cancel)."""

    task: Task
    task_id: str
    state: TaskState
    context_id: str | None = None
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _extract_text_from_parts(parts: list[Part] | None) -> str:
    """Extract text content from message parts."""
    if not parts:
        return ""
    texts = []
    for part in parts:
        if hasattr(part, "root") and hasattr(part.root, "text"):
            texts.append(part.root.text)
        elif hasattr(part, "text"):
            texts.append(part.text)
    return "\n".join(t for t in texts if t)


def _extract_text_from_task(task: Task) -> str:
    """Extract text from task artifacts and history."""
    texts = []
    if task.artifacts:
        for artifact in task.artifacts:
            if artifact.parts:
                texts.append(_extract_text_from_parts(artifact.parts))
    if task.history:
        for msg in task.history:
            if msg.role == Role.agent and msg.parts:
                texts.append(_extract_text_from_parts(msg.parts))
    return "\n".join(t for t in texts if t)


class A2AService:
    """High-level service for A2A protocol operations.

    Wraps the a2a-sdk Client and provides a simplified interface
    for common operations. Designed to be shared between CLI and TUI.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        agent_url: str,
        streaming: bool = True,
        push_notification_url: str | None = None,
        push_notification_token: str | None = None,
    ):
        """Initialize the A2A service.

        Args:
            http_client: Async HTTP client to use for requests
            agent_url: Base URL of the A2A agent
            streaming: Whether to prefer streaming when available
            push_notification_url: Optional webhook URL for push notifications
            push_notification_token: Optional token for push notification auth
        """
        self.http_client = http_client
        self.agent_url = agent_url
        self.streaming = streaming
        self.push_notification_url = push_notification_url
        self.push_notification_token = push_notification_token
        self._client: Client | None = None
        self._card: AgentCard | None = None

    async def get_card(self) -> AgentCard:
        """Fetch and cache the agent card.

        Returns:
            The agent's card with metadata and capabilities
        """
        if self._card is None:
            log.info("Fetching agent card from %s", self.agent_url)
            resolver = A2ACardResolver(self.http_client, self.agent_url)
            self._card = await resolver.get_agent_card()
            log.info("Connected to agent: %s", self._card.name)
        return self._card

    async def _get_client(self) -> Client:
        """Get or create the A2A client.

        Returns:
            Configured A2A client instance
        """
        if self._client is None:
            card = await self.get_card()
            push_configs: list[PushNotificationConfig] = []
            if self.push_notification_url:
                push_configs.append(
                    PushNotificationConfig(
                        url=self.push_notification_url,
                        token=self.push_notification_token,
                    )
                )
                log.info("Push notification config: %s", self.push_notification_url)
            config = ClientConfig(
                httpx_client=self.http_client,
                supported_transports=[TransportProtocol.jsonrpc],
                streaming=self.streaming,
                push_notification_configs=push_configs,
            )
            factory = ClientFactory(config)
            self._client = factory.create(card)
            log.debug("Created A2A client for %s", card.name)
        return self._client

    @property
    def supports_streaming(self) -> bool:
        """Check if the agent supports streaming."""
        if self._card and self._card.capabilities:
            return bool(self._card.capabilities.streaming)
        return False

    @property
    def supports_push_notifications(self) -> bool:
        """Check if the agent supports push notifications."""
        if self._card and self._card.capabilities:
            return bool(self._card.capabilities.push_notifications)
        return False

    def _build_message(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> Message:
        """Build a user message.

        Args:
            text: Message content
            context_id: Optional context ID for conversation continuity
            task_id: Optional task ID to continue

        Returns:
            Properly formatted Message object
        """
        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=text))],
            context_id=context_id,
            task_id=task_id,
        )

    async def send(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> SendResult:
        """Send a message to the agent and wait for completion.

        This method collects all streaming events and returns the final result.

        Args:
            text: Message to send
            context_id: Optional context ID for conversation continuity
            task_id: Optional task ID to continue

        Returns:
            SendResult with task state, extracted text, and IDs
        """
        client = await self._get_client()
        message = self._build_message(text, context_id, task_id)

        log.info("Sending message: %s", text[:50] if len(text) > 50 else text)

        result = SendResult()
        last_task: Task | None = None

        async for event in client.send_message(message):
            if isinstance(event, Message):
                result.message = event
                result.context_id = event.context_id
                result.task_id = event.task_id
                result.text = _extract_text_from_parts(event.parts)
                log.debug("Received message response")
            elif isinstance(event, tuple):
                task, update = event
                last_task = task
                result.task = task
                result.task_id = task.id
                result.context_id = task.context_id
                if task.status:
                    result.state = task.status.state
                log.debug(
                    "Received task update: %s",
                    task.status.state if task.status else "unknown",
                )

        if last_task:
            result.text = _extract_text_from_task(last_task)
            result.raw = (
                last_task.model_dump() if hasattr(last_task, "model_dump") else {}
            )
        elif result.message:
            result.raw = (
                result.message.model_dump()
                if hasattr(result.message, "model_dump")
                else {}
            )

        log.info("Send complete: task_id=%s, state=%s", result.task_id, result.state)
        return result

    async def stream(
        self,
        text: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Send a message and stream responses as they arrive.

        Args:
            text: Message to send
            context_id: Optional context ID for conversation continuity
            task_id: Optional task ID to continue

        Yields:
            StreamEvent objects as they are received
        """
        client = await self._get_client()
        message = self._build_message(text, context_id, task_id)

        log.info("Streaming message: %s", text[:50] if len(text) > 50 else text)

        async for event in client.send_message(message):
            if isinstance(event, Message):
                yield StreamEvent(
                    event_type="message",
                    message=event,
                    context_id=event.context_id,
                    task_id=event.task_id,
                    text=_extract_text_from_parts(event.parts),
                )
            elif isinstance(event, tuple):
                task, update = event
                if isinstance(update, TaskStatusUpdateEvent):
                    status_text = ""
                    if update.status and update.status.message:
                        status_text = str(update.status.message)
                    yield StreamEvent(
                        event_type="status",
                        task=task,
                        status=update,
                        context_id=task.context_id,
                        task_id=task.id,
                        state=update.status.state if update.status else None,
                        text=status_text,
                    )
                elif isinstance(update, TaskArtifactUpdateEvent):
                    artifact_text = ""
                    if update.artifact and update.artifact.parts:
                        artifact_text = _extract_text_from_parts(update.artifact.parts)
                    yield StreamEvent(
                        event_type="artifact",
                        task=task,
                        artifact=update,
                        context_id=task.context_id,
                        task_id=task.id,
                        state=task.status.state if task.status else None,
                        text=artifact_text,
                    )
                else:
                    yield StreamEvent(
                        event_type="task",
                        task=task,
                        context_id=task.context_id,
                        task_id=task.id,
                        state=task.status.state if task.status else None,
                        text=_extract_text_from_task(task),
                    )

    async def get_task(
        self,
        task_id: str,
        history_length: int | None = None,
    ) -> TaskResult:
        """Get the current state of a task.

        Args:
            task_id: ID of the task to retrieve
            history_length: Optional number of history messages to include

        Returns:
            TaskResult with task state and details
        """
        client = await self._get_client()

        params = TaskQueryParams(id=task_id, history_length=history_length)
        log.info("Getting task: %s", task_id)

        task = await client.get_task(params)

        return TaskResult(
            task=task,
            task_id=task.id,
            state=task.status.state if task.status else TaskState.unknown,
            context_id=task.context_id,
            text=_extract_text_from_task(task),
            raw=task.model_dump() if hasattr(task, "model_dump") else {},
        )

    async def cancel_task(self, task_id: str) -> TaskResult:
        """Cancel a running task.

        Args:
            task_id: ID of the task to cancel

        Returns:
            TaskResult with updated task state
        """
        client = await self._get_client()

        params = TaskIdParams(id=task_id)
        log.info("Canceling task: %s", task_id)

        task = await client.cancel_task(params)

        return TaskResult(
            task=task,
            task_id=task.id,
            state=task.status.state if task.status else TaskState.unknown,
            context_id=task.context_id,
            text=_extract_text_from_task(task),
            raw=task.model_dump() if hasattr(task, "model_dump") else {},
        )

    async def resubscribe(self, task_id: str) -> AsyncIterator[StreamEvent]:
        """Resubscribe to a task's event stream.

        Args:
            task_id: ID of the task to resubscribe to

        Yields:
            StreamEvent objects as they are received
        """
        client = await self._get_client()

        params = TaskIdParams(id=task_id)
        log.info("Resubscribing to task: %s", task_id)

        async for event in client.resubscribe(params):
            task, update = event
            if isinstance(update, TaskStatusUpdateEvent):
                yield StreamEvent(
                    event_type="status",
                    task=task,
                    status=update,
                    context_id=task.context_id,
                    task_id=task.id,
                    state=update.status.state if update.status else None,
                )
            elif isinstance(update, TaskArtifactUpdateEvent):
                artifact_text = ""
                if update.artifact and update.artifact.parts:
                    artifact_text = _extract_text_from_parts(update.artifact.parts)
                yield StreamEvent(
                    event_type="artifact",
                    task=task,
                    artifact=update,
                    context_id=task.context_id,
                    task_id=task.id,
                    state=task.status.state if task.status else None,
                    text=artifact_text,
                )
            else:
                yield StreamEvent(
                    event_type="task",
                    task=task,
                    context_id=task.context_id,
                    task_id=task.id,
                    state=task.status.state if task.status else None,
                    text=_extract_text_from_task(task),
                )

    async def set_push_config(
        self,
        task_id: str,
        url: str,
        token: str | None = None,
    ) -> TaskPushNotificationConfig:
        """Set push notification configuration for a task.

        Args:
            task_id: ID of the task
            url: Webhook URL to receive notifications
            token: Optional authentication token

        Returns:
            The created push notification configuration
        """
        client = await self._get_client()

        from a2a.types import PushNotificationConfig

        config = TaskPushNotificationConfig(
            task_id=task_id,
            push_notification_config=PushNotificationConfig(
                url=url,
                token=token,
            ),
        )
        log.info("Setting push config for task %s: %s", task_id, url)

        return await client.set_task_callback(config)

    async def get_push_config(
        self,
        task_id: str,
        config_id: str,
    ) -> TaskPushNotificationConfig:
        """Get push notification configuration for a task.

        Args:
            task_id: ID of the task
            config_id: ID of the push config

        Returns:
            The push notification configuration
        """
        client = await self._get_client()

        params = GetTaskPushNotificationConfigParams(
            id=task_id,
            push_notification_config_id=config_id,
        )
        log.info("Getting push config %s for task %s", config_id, task_id)

        return await client.get_task_callback(params)
