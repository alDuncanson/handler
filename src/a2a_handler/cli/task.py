"""Task commands for managing A2A tasks."""

import asyncio
from typing import Optional

import rich_click as click

from a2a_handler.common import Output, get_logger
from a2a_handler.service import A2AService, TaskResult

from ._helpers import build_http_client, handle_client_error

log = get_logger(__name__)


@click.group()
def task() -> None:
    """Manage A2A tasks."""
    pass


@task.command("get")
@click.argument("agent_url")
@click.argument("task_id")
@click.option(
    "--history-length", "-n", type=int, help="Number of history messages to include"
)
def task_get(
    agent_url: str,
    task_id: str,
    history_length: Optional[int],
) -> None:
    """Retrieve the current status of a task."""
    log.info("Getting task %s from %s", task_id, agent_url)

    async def do_get() -> None:
        output = Output()
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)
                result = await service.get_task(task_id, history_length)
                _format_task_result(result, output)
        except Exception as e:
            handle_client_error(e, agent_url, output)
            raise click.Abort()

    asyncio.run(do_get())


@task.command("cancel")
@click.argument("agent_url")
@click.argument("task_id")
def task_cancel(agent_url: str, task_id: str) -> None:
    """Request cancellation of a task."""
    log.info("Canceling task %s at %s", task_id, agent_url)

    async def do_cancel() -> None:
        output = Output()
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                output.dim(f"Canceling task {task_id}...")

                result = await service.cancel_task(task_id)
                _format_task_result(result, output)

                output.success("Task canceled")

        except Exception as e:
            handle_client_error(e, agent_url, output)
            raise click.Abort()

    asyncio.run(do_cancel())


@task.command("resubscribe")
@click.argument("agent_url")
@click.argument("task_id")
def task_resubscribe(agent_url: str, task_id: str) -> None:
    """Resubscribe to a task's SSE stream after disconnection."""
    log.info("Resubscribing to task %s at %s", task_id, agent_url)

    async def do_resubscribe() -> None:
        output = Output()
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                output.dim(f"Resubscribing to task {task_id}...")

                async for event in service.resubscribe(task_id):
                    if event.event_type == "status":
                        output.state(
                            "Status",
                            event.state.value if event.state else "unknown",
                        )
                    elif event.text:
                        output.line(event.text)

        except Exception as e:
            handle_client_error(e, agent_url, output)
            raise click.Abort()

    asyncio.run(do_resubscribe())


def _format_task_result(result: TaskResult, output: Output) -> None:
    """Format and display a task result."""
    output.blank()
    output.field("Task ID", result.task_id, dim_value=True)
    output.state("State", result.state.value)
    if result.context_id:
        output.field("Context ID", result.context_id, dim_value=True)

    if result.text:
        output.blank()
        output.markdown(result.text)


@task.group("notification")
def task_notification() -> None:
    """Manage push notification configurations for tasks."""
    pass


@task_notification.command("set")
@click.argument("agent_url")
@click.argument("task_id")
@click.option("--url", "-u", required=True, help="Webhook URL to receive notifications")
@click.option("--token", "-t", help="Authentication token for the webhook")
def notification_set(
    agent_url: str,
    task_id: str,
    url: str,
    token: Optional[str],
) -> None:
    """Configure a push notification webhook for a task."""
    log.info("Setting push config for task %s at %s", task_id, agent_url)

    async def do_set() -> None:
        output = Output()
        try:
            async with build_http_client() as http_client:
                service = A2AService(http_client, agent_url)

                output.dim(f"Setting notification config for task {task_id}...")

                config = await service.set_push_config(task_id, url, token)

                output.success("Push notification config set")
                output.field("Task ID", config.task_id)
                if config.push_notification_config:
                    pnc = config.push_notification_config
                    output.field("URL", pnc.url)
                    if pnc.token:
                        output.field("Token", f"{pnc.token[:20]}...")
                    if pnc.id:
                        output.field("Config ID", pnc.id)

        except Exception as e:
            handle_client_error(e, agent_url, output)
            raise click.Abort()

    asyncio.run(do_set())
