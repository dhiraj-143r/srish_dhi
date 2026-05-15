"""
InboxPilot — AgentMail Tool Wrapper
Handles inbox creation, email sending, receiving, threading, and webhook registration.
Uses AgentMail SDK v0.5.0 API structure.
"""
import logging
from agentmail import AgentMail
from config import config

logger = logging.getLogger("inbox-pilot.tools.agentmail")

# Initialize AgentMail client
client = AgentMail(api_key=config.AGENTMAIL_API_KEY)

# Store the inbox info after creation
_inbox_cache: dict = {}


async def get_or_create_inbox() -> dict:
    """Create or retrieve the agent's email inbox."""
    if "default" in _inbox_cache:
        return _inbox_cache["default"]

    try:
        inboxes = client.inboxes.list()
        if inboxes.inboxes:
            inbox = inboxes.inboxes[0]
            inbox_data = {
                "inbox_id": inbox.inbox_id,
                "email_address": inbox.email,
                "pod_id": inbox.pod_id,
            }
            _inbox_cache["default"] = inbox_data
            logger.info(f"Found existing inbox: {inbox.email}")
            return inbox_data
    except Exception as e:
        logger.warning(f"Could not list inboxes: {e}")

    try:
        inbox = client.inboxes.create()
        inbox_data = {
            "inbox_id": inbox.inbox_id,
            "email_address": inbox.email,
            "pod_id": inbox.pod_id,
        }
        _inbox_cache["default"] = inbox_data
        logger.info(f"Created new inbox: {inbox.email}")
        return inbox_data
    except Exception as e:
        logger.error(f"Failed to create inbox: {e}")
        raise


async def get_message(inbox_id: str, message_id: str) -> dict:
    """Fetch full message content from AgentMail."""
    try:
        message = client.inboxes.messages.get(inbox_id=inbox_id, message_id=message_id)
        sender = getattr(message, 'from_', '') or getattr(message, 'sender', '')
        if not sender:
            sender = getattr(message, 'from_address', '')
        return {
            "message_id": getattr(message, 'message_id', message_id),
            "thread_id": getattr(message, 'thread_id', None),
            "sender": sender,
            "to": getattr(message, 'to', []),
            "subject": getattr(message, 'subject', ''),
            "text": getattr(message, 'text', ''),
            "html": getattr(message, 'html', ''),
            "attachments": getattr(message, 'attachments', []),
            "received_at": str(getattr(message, 'created_at', '')),
        }
    except Exception as e:
        logger.error(f"Failed to get message {message_id}: {e}")
        raise


async def list_threads(inbox_id: str) -> list:
    """List recent threads in the inbox."""
    try:
        threads = client.inboxes.threads.list(inbox_id=inbox_id)
        return threads.threads if hasattr(threads, 'threads') else []
    except Exception as e:
        logger.error(f"Failed to list threads: {e}")
        return []


async def get_thread(inbox_id: str, thread_id: str) -> dict:
    """Get full thread with all messages for conversation context."""
    try:
        thread = client.inboxes.threads.get(inbox_id=inbox_id, thread_id=thread_id)
        return {
            "thread_id": getattr(thread, 'thread_id', thread_id),
            "subject": getattr(thread, 'subject', ''),
            "messages": getattr(thread, 'messages', []),
            "message_count": len(getattr(thread, 'messages', [])),
        }
    except Exception as e:
        logger.error(f"Failed to get thread {thread_id}: {e}")
        return {"thread_id": thread_id, "messages": [], "message_count": 0}


async def send_reply(inbox_id: str, to: str, subject: str, body: str, thread_id: str = None) -> dict:
    """Send an email via AgentMail."""
    try:
        to_list = to if isinstance(to, list) else [to]
        message = client.inboxes.messages.send(
            inbox_id=inbox_id,
            to=to_list,
            subject=subject,
            text=body,
        )
        result = {
            "status": "sent",
            "message_id": getattr(message, 'message_id', 'unknown'),
            "to": to,
            "subject": subject,
        }
        logger.info(f"Reply sent to {to}: {subject}")
        return result
    except Exception as e:
        logger.error(f"Failed to send reply to {to}: {e}")
        return {"status": "failed", "error": str(e)}


async def reply_to_message(inbox_id: str, message_id: str, body: str) -> dict:
    """Reply to a specific message in a thread."""
    try:
        message = client.inboxes.messages.reply(
            inbox_id=inbox_id,
            message_id=message_id,
            text=body,
        )
        result = {
            "status": "sent",
            "message_id": getattr(message, 'message_id', 'unknown'),
        }
        logger.info(f"Reply sent to message {message_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to reply to {message_id}: {e}")
        return {"status": "failed", "error": str(e)}


async def register_webhook(webhook_url: str) -> dict:
    """Register a webhook URL for incoming email notifications."""
    try:
        webhook = client.webhooks.create(
            url=webhook_url,
            event_types=["message.received"]
        )
        result = {
            "webhook_id": getattr(webhook, 'webhook_id', getattr(webhook, 'id', 'unknown')),
            "url": webhook_url,
            "status": "registered",
        }
        logger.info(f"Webhook registered: {webhook_url}")
        return result
    except Exception as e:
        logger.error(f"Failed to register webhook: {e}")
        return {"status": "failed", "error": str(e)}


async def list_messages(inbox_id: str) -> list:
    """List recent messages in the inbox."""
    try:
        messages = client.inboxes.messages.list(inbox_id=inbox_id)
        return messages.messages if hasattr(messages, 'messages') else []
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        return []
