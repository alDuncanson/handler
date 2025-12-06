"""Local webhook server for receiving A2A push notifications.

This module provides a simple HTTP server that can receive push notifications
from A2A agents for testing purposes.
"""

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a_handler.common import console, get_logger

log = get_logger(__name__)

MAX_NOTIFICATIONS = 100


@dataclass
class Notification:
    """A received push notification."""

    timestamp: datetime
    task_id: str | None
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass
class NotificationStore:
    """In-memory store for received notifications."""

    notifications: deque[Notification] = field(
        default_factory=lambda: deque(maxlen=MAX_NOTIFICATIONS)
    )

    def add(self, notification: Notification) -> None:
        """Add a notification to the store."""
        self.notifications.append(notification)

    def get_all(self) -> list[Notification]:
        """Get all stored notifications."""
        return list(self.notifications)

    def clear(self) -> None:
        """Clear all stored notifications."""
        self.notifications.clear()


notification_store = NotificationStore()


async def handle_notification(request: Request) -> JSONResponse:
    """Handle incoming push notifications from A2A agents."""
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        log.warning("Received invalid JSON in push notification")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    headers = dict(request.headers)
    task_id = payload.get("id") or payload.get("task_id")

    notification = Notification(
        timestamp=datetime.now(),
        task_id=task_id,
        payload=payload,
        headers=headers,
    )
    notification_store.add(notification)

    log.info("Received push notification for task: %s", task_id)

    console.print("\n[bold cyan]Push Notification Received[/bold cyan]")
    console.print(f"[dim]Timestamp:[/dim] {notification.timestamp.isoformat()}")
    if task_id:
        console.print(f"[dim]Task ID:[/dim] {task_id}")

    status = payload.get("status", {})
    if status:
        state = status.get("state", "unknown")
        console.print(f"[dim]State:[/dim] {state}")

    token = headers.get("x-a2a-notification-token")
    if token:
        console.print(f"[dim]Token:[/dim] {token[:20]}...")

    console.print()
    console.print_json(json.dumps(payload, indent=2, default=str))
    console.print()

    return JSONResponse({"status": "ok", "received": True})


async def handle_validation(request: Request) -> JSONResponse:
    """Handle GET requests for webhook validation."""
    log.info("Webhook validation request received")
    return JSONResponse({"status": "ok", "message": "Webhook is active"})


async def handle_list(request: Request) -> JSONResponse:
    """List all received notifications."""
    notifications = notification_store.get_all()
    return JSONResponse(
        {
            "count": len(notifications),
            "notifications": [
                {
                    "timestamp": n.timestamp.isoformat(),
                    "task_id": n.task_id,
                    "payload": n.payload,
                }
                for n in notifications
            ],
        }
    )


async def handle_clear(request: Request) -> JSONResponse:
    """Clear all stored notifications."""
    notification_store.clear()
    log.info("Cleared all stored notifications")
    return JSONResponse({"status": "ok", "message": "Notifications cleared"})


def create_webhook_app() -> Starlette:
    """Create the webhook Starlette application."""
    routes = [
        Route("/webhook", handle_notification, methods=["POST"]),
        Route("/webhook", handle_validation, methods=["GET"]),
        Route("/notifications", handle_list, methods=["GET"]),
        Route("/notifications/clear", handle_clear, methods=["POST"]),
    ]
    return Starlette(routes=routes)


def run_webhook_server(host: str = "127.0.0.1", port: int = 9000) -> None:
    """Start the webhook server.

    Args:
        host: Host address to bind to
        port: Port number to bind to
    """
    console.print(f"\n[bold]Starting webhook server on [url]{host}:{port}[/url][/bold]")
    console.print()
    console.print("[dim]Endpoints:[/dim]")
    console.print(f"  POST http://{host}:{port}/webhook - Receive notifications")
    console.print(f"  GET  http://{host}:{port}/webhook - Validation check")
    console.print(f"  GET  http://{host}:{port}/notifications - List received")
    console.print(f"  POST http://{host}:{port}/notifications/clear - Clear stored")
    console.print()
    console.print(
        f"[bold green]Use this URL for push notifications:[/bold green] "
        f"http://{host}:{port}/webhook"
    )
    console.print()

    app = create_webhook_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")
