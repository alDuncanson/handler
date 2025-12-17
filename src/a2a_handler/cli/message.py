"""Message commands for sending messages to A2A agents."""

import asyncio
from typing import Optional

import rich_click as click

from a2a_handler.auth import AuthCredentials, create_api_key_auth, create_bearer_auth
from a2a_handler.common import Output, get_logger
from a2a_handler.service import A2AService, SendResult
from a2a_handler.session import get_credentials, get_session, update_session

from ._helpers import build_http_client, handle_client_error

log = get_logger(__name__)


@click.group()
def message() -> None:
    """Send messages to A2A agents."""
    pass


@message.command("send")
@click.argument("agent_url")
@click.argument("text")
@click.option("--stream", "-s", is_flag=True, help="Stream responses in real-time")
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Task ID to continue")
@click.option(
    "--continue", "-C", "use_session", is_flag=True, help="Continue from saved session"
)
@click.option("--push-url", help="Webhook URL for push notifications")
@click.option("--push-token", help="Authentication token for push notifications")
@click.option("--bearer", "-b", "bearer_token", help="Bearer token (overrides saved)")
@click.option("--api-key", "-k", help="API key (overrides saved)")
def message_send(
    agent_url: str,
    text: str,
    stream: bool,
    context_id: Optional[str],
    task_id: Optional[str],
    use_session: bool,
    push_url: Optional[str],
    push_token: Optional[str],
    bearer_token: Optional[str],
    api_key: Optional[str],
) -> None:
    """Send a message to an agent and receive a response."""
    log.info("Sending message to %s", agent_url)

    if use_session and not context_id:
        session = get_session(agent_url)
        if session.context_id:
            context_id = session.context_id
            log.info("Using saved context: %s", context_id)

    credentials: AuthCredentials | None = None
    if bearer_token:
        credentials = create_bearer_auth(bearer_token)
    elif api_key:
        credentials = create_api_key_auth(api_key)
    else:
        credentials = get_credentials(agent_url)

    async def do_send() -> None:
        output = Output()
        try:
            async with build_http_client() as http_client:
                service = A2AService(
                    http_client,
                    agent_url,
                    enable_streaming=stream,
                    push_notification_url=push_url,
                    push_notification_token=push_token,
                    credentials=credentials,
                )

                output.dim(f"Sending to {agent_url}...")

                if stream:
                    await _stream_message(
                        service, text, context_id, task_id, agent_url, output
                    )
                else:
                    result = await service.send(text, context_id, task_id)
                    update_session(agent_url, result.context_id, result.task_id)
                    _format_send_result(result, output)

        except Exception as e:
            handle_client_error(e, agent_url, output)
            raise click.Abort()

    asyncio.run(do_send())


@message.command("stream")
@click.argument("agent_url")
@click.argument("text")
@click.option("--context-id", help="Context ID for conversation continuity")
@click.option("--task-id", help="Task ID to continue")
@click.option(
    "--continue", "-C", "use_session", is_flag=True, help="Continue from saved session"
)
@click.option("--push-url", help="Webhook URL for push notifications")
@click.option("--push-token", help="Authentication token for push notifications")
@click.option("--bearer", "-b", "bearer_token", help="Bearer token (overrides saved)")
@click.option("--api-key", "-k", help="API key (overrides saved)")
@click.pass_context
def message_stream(
    ctx: click.Context,
    agent_url: str,
    text: str,
    context_id: Optional[str],
    task_id: Optional[str],
    use_session: bool,
    push_url: Optional[str],
    push_token: Optional[str],
    bearer_token: Optional[str],
    api_key: Optional[str],
) -> None:
    """Send a message and stream the response in real-time."""
    ctx.invoke(
        message_send,
        agent_url=agent_url,
        text=text,
        stream=True,
        context_id=context_id,
        task_id=task_id,
        use_session=use_session,
        push_url=push_url,
        push_token=push_token,
        bearer_token=bearer_token,
        api_key=api_key,
    )


async def _stream_message(
    service: A2AService,
    text: str,
    context_id: Optional[str],
    task_id: Optional[str],
    agent_url: str,
    output: Output,
) -> None:
    """Stream a message and handle events."""
    collected_text: list[str] = []
    last_context_id: str | None = None
    last_task_id: str | None = None
    last_state = None

    async for event in service.stream(text, context_id, task_id):
        last_context_id = event.context_id or last_context_id
        last_task_id = event.task_id or last_task_id
        last_state = event.state or last_state

        if event.text and event.text not in collected_text:
            output.line(event.text)
            collected_text.append(event.text)

    update_session(agent_url, last_context_id, last_task_id)

    output.blank()
    if last_context_id:
        output.field("Context ID", last_context_id, dim_value=True)
    if last_task_id:
        output.field("Task ID", last_task_id, dim_value=True)
    if last_state:
        output.state("State", last_state.value)

    if last_state and last_state.value == "auth-required":
        output.blank()
        output.warning("Authentication required")
        output.line("The agent requires authentication to complete this task.")
        output.line(
            "Set credentials with: handler auth set <agent_url> --bearer <token>"
        )


def _format_send_result(result: SendResult, output: Output) -> None:
    """Format and display a send result."""
    output.blank()
    if result.context_id:
        output.field("Context ID", result.context_id, dim_value=True)
    if result.task_id:
        output.field("Task ID", result.task_id, dim_value=True)
    if result.state:
        output.state("State", result.state.value)

    output.blank()
    if result.needs_auth:
        output.warning("Authentication required")
        output.line("The agent requires authentication to complete this task.")
        output.line(
            "Set credentials with: handler auth set <agent_url> --bearer <token>"
        )
        output.line(
            "Or provide inline: handler message send <agent_url> --bearer <token> ..."
        )
    elif result.text:
        output.markdown(result.text)
    else:
        output.dim("No text content in response")
