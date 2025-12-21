"""Tasks panel component for viewing task history and details."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message as TextualMessage
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, Static

from a2a_handler.common import get_logger

if TYPE_CHECKING:
    from a2a.types import Task, TaskState

logger = get_logger(__name__)


class TaskEntry:
    """Represents a task entry for display."""

    def __init__(self, task: Task, received_at: datetime | None = None) -> None:
        self.task = task
        self.received_at = received_at or datetime.now()

    @property
    def task_id(self) -> str:
        return self.task.id

    @property
    def context_id(self) -> str:
        return self.task.context_id

    @property
    def state(self) -> TaskState | None:
        if self.task.status:
            return self.task.status.state
        return None

    @property
    def state_str(self) -> str:
        return str(self.state.value) if self.state else "unknown"


class TaskListItem(ListItem):
    """A single task item in the list."""

    def __init__(
        self,
        entry: TaskEntry,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.entry = entry

    def compose(self) -> ComposeResult:
        time_str = self.entry.received_at.strftime("%H:%M:%S")
        state_str = self.entry.state_str
        task_id_short = self.entry.task_id[:8] if self.entry.task_id else "?"
        yield Label(f"{time_str}  [{state_str}]  {task_id_short}...")


class TaskDetailPanel(VerticalScroll):
    """Panel showing detailed information about the selected task."""

    def compose(self) -> ComposeResult:
        yield Static("Select a task to view details", id="task-detail-placeholder")
        yield Static("", id="task-detail-content", classes="hidden")

    def show_task(self, entry: TaskEntry | None) -> None:
        placeholder = self.query_one("#task-detail-placeholder", Static)
        content = self.query_one("#task-detail-content", Static)

        if entry is None:
            placeholder.remove_class("hidden")
            content.add_class("hidden")
            return

        placeholder.add_class("hidden")
        content.remove_class("hidden")

        task = entry.task
        lines = [
            f"[b]Task ID:[/b] {task.id}",
            f"[b]Context ID:[/b] {task.context_id}",
            f"[b]State:[/b] {entry.state_str}",
            f"[b]Received:[/b] {entry.received_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if task.status:
            if task.status.timestamp:
                lines.append(f"[b]Last Updated:[/b] {task.status.timestamp}")
            if task.status.message:
                msg = task.status.message
                if hasattr(msg, "parts") and msg.parts:
                    from a2a_handler.service import extract_text_from_message_parts

                    text = extract_text_from_message_parts(msg.parts)
                    if text:
                        lines.append(f"[b]Status Message:[/b] {text[:200]}")

        if task.artifacts:
            lines.append("")
            lines.append(f"[b]Artifacts:[/b] {len(task.artifacts)}")
            for i, artifact in enumerate(task.artifacts):
                artifact_id = artifact.artifact_id or f"artifact-{i}"
                lines.append(f"  • {artifact_id}")
                if artifact.parts:
                    from a2a_handler.service import extract_text_from_message_parts

                    text = extract_text_from_message_parts(artifact.parts)
                    if text:
                        preview = text[:100].replace("\n", " ")
                        if len(text) > 100:
                            preview += "..."
                        lines.append(f"    {preview}")

        if task.history:
            lines.append("")
            lines.append(f"[b]History:[/b] {len(task.history)} messages")

        content.update("\n".join(lines))


class TasksPanel(Container):
    """Panel with split view: task list on left, details on right."""

    BINDINGS = [
        Binding("j", "cursor_down", "↓ Select", show=True, key_display="j/↓"),
        Binding("k", "cursor_up", "↑ Select", show=True, key_display="k/↑"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "select_task", "View", show=True),
        Binding("y", "copy_task_id", "Copy ID", show=True),
        Binding("Y", "copy_context_id", "Copy Ctx", show=True),
    ]

    can_focus = True

    selected_index: reactive[int] = reactive(0)
    _tasks: list[TaskEntry] = []

    class TaskSelected(TextualMessage):
        """Posted when a task is selected."""

        def __init__(self, entry: TaskEntry) -> None:
            super().__init__()
            self.entry = entry

    def compose(self) -> ComposeResult:
        with Horizontal(id="tasks-split"):
            yield ListView(id="tasks-list")
            yield TaskDetailPanel(id="task-detail")

    def on_mount(self) -> None:
        self._tasks = []
        logger.debug("Tasks panel mounted")

    def _get_list_view(self) -> ListView:
        return self.query_one("#tasks-list", ListView)

    def _get_detail_panel(self) -> TaskDetailPanel:
        return self.query_one("#task-detail", TaskDetailPanel)

    def add_task(self, task: Task) -> None:
        """Add a task to the list."""
        entry = TaskEntry(task)
        self._tasks.insert(0, entry)
        list_view = self._get_list_view()
        list_view.insert(0, [TaskListItem(entry)])
        logger.debug("Added task %s to tasks panel", task.id[:8])

        if len(self._tasks) == 1:
            self._update_detail()

    def update_task(self, task: Task) -> None:
        """Update an existing task or add if new."""
        for i, entry in enumerate(self._tasks):
            if entry.task_id == task.id:
                self._tasks[i] = TaskEntry(task, entry.received_at)
                list_view = self._get_list_view()
                children = list(list_view.children)
                if i < len(children):
                    old_item = children[i]
                    new_item = TaskListItem(self._tasks[i])
                    old_item.remove()
                    list_view.insert(i, [new_item])

                if i == self.selected_index:
                    self._update_detail()
                logger.debug("Updated task %s", task.id[:8])
                return

        self.add_task(task)

    def _update_detail(self) -> None:
        """Update the detail panel with the currently selected task."""
        detail = self._get_detail_panel()
        if 0 <= self.selected_index < len(self._tasks):
            detail.show_task(self._tasks[self.selected_index])
        else:
            detail.show_task(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        list_view = self._get_list_view()
        if event.item and event.item in list_view.children:
            self.selected_index = list_view.children.index(event.item)
            self._update_detail()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle list item highlight (cursor movement)."""
        list_view = self._get_list_view()
        if event.item and event.item in list_view.children:
            self.selected_index = list_view.children.index(event.item)
            self._update_detail()

    def action_cursor_down(self) -> None:
        list_view = self._get_list_view()
        list_view.action_cursor_down()

    def action_cursor_up(self) -> None:
        list_view = self._get_list_view()
        list_view.action_cursor_up()

    def action_select_task(self) -> None:
        list_view = self._get_list_view()
        list_view.action_select_cursor()

    def action_copy_task_id(self) -> None:
        """Copy the selected task ID to clipboard."""
        if 0 <= self.selected_index < len(self._tasks):
            task_id = self._tasks[self.selected_index].task_id
            self.app.copy_to_clipboard(task_id)
            self.notify(f"Copied task ID: {task_id[:16]}...")

    def action_copy_context_id(self) -> None:
        """Copy the selected context ID to clipboard."""
        if 0 <= self.selected_index < len(self._tasks):
            context_id = self._tasks[self.selected_index].context_id
            self.app.copy_to_clipboard(context_id)
            self.notify(f"Copied context ID: {context_id[:16]}...")

    def get_selected_task(self) -> TaskEntry | None:
        """Get the currently selected task entry."""
        if 0 <= self.selected_index < len(self._tasks):
            return self._tasks[self.selected_index]
        return None

    def clear(self) -> None:
        """Clear all tasks."""
        self._tasks = []
        list_view = self._get_list_view()
        list_view.clear()
        self._update_detail()
        logger.info("Cleared tasks panel")
