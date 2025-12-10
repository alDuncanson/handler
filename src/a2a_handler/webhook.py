"""Webhook server for receiving A2A push notifications.

Provides an HTTP server for receiving and displaying push notifications from A2A agents.
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

logger = get_logger(__name__)

DEFAULT_MAX_STORED_NOTIFICATIONS = 100


@dataclass
class PushNotification:
    """A received push notification."""

    timestamp: datetime
    task_id: str | None
    payload: dict[str, Any]
    headers: dict[str, str]


@dataclass
class PushNotificationStore:
    """In-memory store for received notifications."""

    notifications: deque[PushNotification] = field(
        default_factory=lambda: deque(maxlen=DEFAULT_MAX_STORED_NOTIFICATIONS)
    )

    def add_notification(self, notification: PushNotification) -> None:
        """Add a notification to the store."""
        self.notifications.append(notification)
        logger.debug(
            "Stored notification for task: %s (total: %d)",
            notification.task_id,
            len(self.notifications),
        )

    def get_all_notifications(self) -> list[PushNotification]:
        """Get all stored notifications."""
        return list(self.notifications)

    def clear_all_notifications(self) -> None:
        """Clear all stored notifications."""
        notification_count = len(self.notifications)
        self.notifications.clear()
        logger.info("Cleared %d stored notifications", notification_count)


notification_store = PushNotificationStore()


async def handle_push_notification(request: Request) -> JSONResponse:
    """Handle incoming push notifications from A2A agents."""
    try:
        request_payload = await request.json()
    except json.JSONDecodeError:
        logger.warning("Received invalid JSON in push notification")
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    request_headers = dict(request.headers)
    task_id = request_payload.get("id") or request_payload.get("task_id")

    notification = PushNotification(
        timestamp=datetime.now(),
        task_id=task_id,
        payload=request_payload,
        headers=request_headers,
    )
    notification_store.add_notification(notification)

    logger.info("Received push notification for task: %s", task_id)

    console.print("\n[bold cyan]Push Notification Received[/bold cyan]")
    console.print(f"[dim]Timestamp:[/dim] {notification.timestamp.isoformat()}")
    if task_id:
        console.print(f"[dim]Task ID:[/dim] {task_id}")

    task_status = request_payload.get("status", {})
    if task_status:
        task_state = task_status.get("state", "unknown")
        console.print(f"[dim]State:[/dim] {task_state}")

    authentication_token = request_headers.get("x-a2a-notification-token")
    if authentication_token:
        console.print(f"[dim]Token:[/dim] {authentication_token[:20]}...")

    console.print()
    console.print_json(json.dumps(request_payload, indent=2, default=str))
    console.print()

    return JSONResponse({"status": "ok", "received": True})


async def handle_webhook_validation(request: Request) -> JSONResponse:
    """Handle GET requests for webhook validation."""
    logger.info("Webhook validation request received")
    return JSONResponse({"status": "ok", "message": "Webhook is active"})


async def handle_list_notifications(request: Request) -> JSONResponse:
    """List all received notifications."""
    all_notifications = notification_store.get_all_notifications()
    logger.debug("Returning %d stored notifications", len(all_notifications))
    return JSONResponse(
        {
            "count": len(all_notifications),
            "notifications": [
                {
                    "timestamp": notification.timestamp.isoformat(),
                    "task_id": notification.task_id,
                    "payload": notification.payload,
                }
                for notification in all_notifications
            ],
        }
    )


async def handle_clear_notifications(request: Request) -> JSONResponse:
    """Clear all stored notifications."""
    notification_store.clear_all_notifications()
    return JSONResponse({"status": "ok", "message": "Notifications cleared"})


def create_webhook_application() -> Starlette:
    """Create the webhook Starlette application."""
    application_routes = [
        Route("/webhook", handle_push_notification, methods=["POST"]),
        Route("/webhook", handle_webhook_validation, methods=["GET"]),
        Route("/notifications", handle_list_notifications, methods=["GET"]),
        Route("/notifications/clear", handle_clear_notifications, methods=["POST"]),
    ]
    return Starlette(routes=application_routes)


def run_webhook_server(
    host: str = "127.0.0.1",
    port: int = 9000,
) -> None:
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

    logger.info("Starting webhook server on %s:%d", host, port)
    webhook_application = create_webhook_application()
    uvicorn.run(webhook_application, host=host, port=port, log_level="warning")
