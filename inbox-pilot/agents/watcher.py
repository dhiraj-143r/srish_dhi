"""
InboxPilot — Watcher Agent
Receives raw webhook payload, fetches full email content from AgentMail,
and parses it into structured state for the pipeline.
"""
import logging
import time
from agents.state import EmailState
from tools import agentmail_tools

logger = logging.getLogger("inbox-pilot.agents.watcher")


async def watcher_agent(state: EmailState) -> dict:
    """
    Parse incoming email from webhook payload.
    Fetches full message content and thread context from AgentMail.
    """
    log = state.get("processing_log", [])
    log.append({"agent": "watcher", "status": "started", "ts": time.time(), "msg": "📨 Parsing incoming email..."})

    payload = state.get("raw_payload", {})
    inbox_id = state.get("inbox_id", "")
    message_id = state.get("message_id", "")

    # Extract from webhook payload if not already set
    if not inbox_id:
        inbox_id = payload.get("inbox_id", "") or payload.get("data", {}).get("inbox_id", "")
    if not message_id:
        message_id = payload.get("message_id", "") or payload.get("data", {}).get("message_id", "")

    # Fetch full message from AgentMail
    try:
        message = await agentmail_tools.get_message(inbox_id, message_id)
    except Exception as e:
        logger.error(f"Failed to fetch message: {e}")
        # Try to extract from payload directly
        message = {
            "message_id": message_id,
            "sender": payload.get("from", "") or payload.get("data", {}).get("from", ""),
            "subject": payload.get("subject", "") or payload.get("data", {}).get("subject", ""),
            "text": payload.get("text", "") or payload.get("data", {}).get("text", ""),
            "html": payload.get("html", ""),
            "attachments": payload.get("attachments", []),
            "thread_id": payload.get("thread_id", ""),
        }

    sender = message.get("sender", "")
    if isinstance(sender, list):
        sender = sender[0] if sender else ""
    elif isinstance(sender, dict):
        sender = sender.get("email", "") or sender.get("address", "")

    subject = message.get("subject", "(no subject)")
    body = message.get("text", "") or ""
    html_body = message.get("html", "") or ""
    attachments = message.get("attachments", []) or []
    thread_id = message.get("thread_id", "")

    # Fetch thread context if available
    thread_messages = []
    if thread_id:
        try:
            thread = await agentmail_tools.get_thread(inbox_id, thread_id)
            thread_messages = thread.get("messages", [])
        except Exception as e:
            logger.warning(f"Could not fetch thread context: {e}")

    log.append({
        "agent": "watcher",
        "status": "completed",
        "ts": time.time(),
        "msg": f"✅ Email parsed: from={sender}, subject='{subject[:50]}', attachments={len(attachments)}"
    })

    return {
        "inbox_id": inbox_id,
        "message_id": message_id,
        "sender": sender,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "thread_id": thread_id,
        "thread_messages": thread_messages,
        "attachments": attachments,
        "has_attachments": len(attachments) > 0,
        "received_at": message.get("received_at", ""),
        "processing_log": log,
    }
