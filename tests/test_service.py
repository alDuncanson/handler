"""Tests for the A2A service layer module."""

from a2a.types import Message, Part, Role, Task, TaskState, TaskStatus, TextPart

from a2a_handler.service import (
    SendResult,
    StreamEvent,
    TaskResult,
    TERMINAL_TASK_STATES,
    extract_text_from_message_parts,
)


def _make_task(
    state: TaskState, task_id: str = "task-123", context_id: str = "ctx-123"
) -> Task:
    """Helper to create a Task with the given state."""
    return Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=state),
    )


def _make_message(context_id: str = "ctx-123", task_id: str | None = None) -> Message:
    """Helper to create a Message."""
    return Message(
        message_id="msg-123",
        role=Role.agent,
        parts=[Part(root=TextPart(text="Hello"))],
        context_id=context_id,
        task_id=task_id,
    )


class TestSendResult:
    """Tests for SendResult dataclass."""

    def test_is_complete_when_completed(self):
        """Test is_complete returns True for completed state."""
        result = SendResult(task=_make_task(TaskState.completed))
        assert result.is_complete is True

    def test_is_complete_when_canceled(self):
        """Test is_complete returns True for canceled state."""
        result = SendResult(task=_make_task(TaskState.canceled))
        assert result.is_complete is True

    def test_is_complete_when_failed(self):
        """Test is_complete returns True for failed state."""
        result = SendResult(task=_make_task(TaskState.failed))
        assert result.is_complete is True

    def test_is_complete_when_rejected(self):
        """Test is_complete returns True for rejected state."""
        result = SendResult(task=_make_task(TaskState.rejected))
        assert result.is_complete is True

    def test_is_complete_when_working(self):
        """Test is_complete returns False for working state."""
        result = SendResult(task=_make_task(TaskState.working))
        assert result.is_complete is False

    def test_is_complete_when_no_state(self):
        """Test is_complete returns False when no task or message."""
        result = SendResult()
        assert result.is_complete is False

    def test_needs_input_when_input_required(self):
        """Test needs_input returns True for input_required state."""
        result = SendResult(task=_make_task(TaskState.input_required))
        assert result.needs_input is True

    def test_needs_input_when_working(self):
        """Test needs_input returns False for working state."""
        result = SendResult(task=_make_task(TaskState.working))
        assert result.needs_input is False

    def test_needs_input_when_no_state(self):
        """Test needs_input returns False when no task or message."""
        result = SendResult()
        assert result.needs_input is False

    def test_context_id_from_task(self):
        """Test context_id is derived from task."""
        result = SendResult(task=_make_task(TaskState.completed, context_id="ctx-456"))
        assert result.context_id == "ctx-456"

    def test_context_id_from_message(self):
        """Test context_id is derived from message when no task."""
        result = SendResult(message=_make_message(context_id="ctx-789"))
        assert result.context_id == "ctx-789"

    def test_task_id_from_task(self):
        """Test task_id is derived from task."""
        result = SendResult(task=_make_task(TaskState.completed, task_id="task-456"))
        assert result.task_id == "task-456"

    def test_task_id_from_message(self):
        """Test task_id is derived from message when no task."""
        result = SendResult(message=_make_message(task_id="task-789"))
        assert result.task_id == "task-789"

    def test_state_from_task(self):
        """Test state is derived from task status."""
        result = SendResult(task=_make_task(TaskState.working))
        assert result.state == TaskState.working


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_create_message_event(self):
        """Test creating a message event with message object."""
        msg = _make_message(context_id="ctx-123", task_id="task-456")
        event = StreamEvent(
            event_type="message",
            message=msg,
            text="Hello, world!",
        )

        assert event.event_type == "message"
        assert event.context_id == "ctx-123"
        assert event.task_id == "task-456"
        assert event.text == "Hello, world!"

    def test_create_status_event(self):
        """Test creating a status event with task object."""
        task = _make_task(TaskState.working, task_id="task-456")
        event = StreamEvent(
            event_type="status",
            task=task,
        )

        assert event.event_type == "status"
        assert event.task_id == "task-456"
        assert event.state == TaskState.working

    def test_context_id_from_task(self):
        """Test context_id derived from task."""
        task = _make_task(TaskState.completed, context_id="ctx-abc")
        event = StreamEvent(event_type="task", task=task)
        assert event.context_id == "ctx-abc"


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_create_task_result(self):
        """Test creating a task result."""
        mock_task = _make_task(
            TaskState.completed, task_id="task-123", context_id="ctx-123"
        )

        result = TaskResult(
            task=mock_task,
            text="Task completed successfully",
        )

        assert result.task_id == "task-123"
        assert result.context_id == "ctx-123"
        assert result.state == TaskState.completed
        assert result.text == "Task completed successfully"

    def test_properties_derived_from_task(self):
        """Test that properties are correctly derived from the SDK Task object."""
        task = _make_task(TaskState.failed, task_id="task-xyz", context_id="ctx-xyz")
        result = TaskResult(task=task)

        assert result.task_id == "task-xyz"
        assert result.context_id == "ctx-xyz"
        assert result.state == TaskState.failed


class TestExtractTextFromMessageParts:
    """Tests for extract_text_from_message_parts function."""

    def test_extract_from_none(self):
        """Test extracting from None returns empty string."""
        result = extract_text_from_message_parts(None)
        assert result == ""

    def test_extract_from_empty_list(self):
        """Test extracting from empty list returns empty string."""
        result = extract_text_from_message_parts([])
        assert result == ""

    def test_extract_from_text_part_with_root(self):
        """Test extracting from TextPart wrapped in Part."""
        parts = [Part(root=TextPart(text="Hello, world!"))]
        result = extract_text_from_message_parts(parts)
        assert result == "Hello, world!"

    def test_extract_multiple_parts(self):
        """Test extracting from multiple parts joins with newlines."""
        parts = [
            Part(root=TextPart(text="First line")),
            Part(root=TextPart(text="Second line")),
        ]
        result = extract_text_from_message_parts(parts)
        assert result == "First line\nSecond line"


class TestTerminalStates:
    """Tests for terminal state constants."""

    def test_terminal_states_include_completed(self):
        """Test that completed is a terminal state."""
        assert TaskState.completed in TERMINAL_TASK_STATES

    def test_terminal_states_include_canceled(self):
        """Test that canceled is a terminal state."""
        assert TaskState.canceled in TERMINAL_TASK_STATES

    def test_terminal_states_include_failed(self):
        """Test that failed is a terminal state."""
        assert TaskState.failed in TERMINAL_TASK_STATES

    def test_terminal_states_include_rejected(self):
        """Test that rejected is a terminal state."""
        assert TaskState.rejected in TERMINAL_TASK_STATES

    def test_working_is_not_terminal(self):
        """Test that working is not a terminal state."""
        assert TaskState.working not in TERMINAL_TASK_STATES
