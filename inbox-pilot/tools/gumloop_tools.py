"""
InboxPilot — Gumloop Tool Wrapper
Triggers Gumloop workflows for task creation, notifications, and digest generation.
Optional — gracefully degrades if not configured.
"""
import logging
from config import config

logger = logging.getLogger("inbox-pilot.tools.gumloop")

# Conditional import
_gumloop_client = None
if config.has_gumloop():
    try:
        from gumloop import GumloopClient
        _gumloop_client = GumloopClient(
            api_key=config.GUMLOOP_API_KEY,
            user_id=config.GUMLOOP_USER_ID,
        )
        logger.info("Gumloop client initialized")
    except ImportError:
        logger.warning("Gumloop SDK not installed — workflows disabled")
    except Exception as e:
        logger.warning(f"Gumloop init failed: {e}")


async def trigger_task_workflow(title: str, description: str, priority: str = "medium", source_email: str = "") -> dict:
    """Trigger a Gumloop workflow to create a task from an email."""
    if not _gumloop_client:
        logger.info(f"Gumloop not configured — task logged locally: {title}")
        return {
            "status": "local_only",
            "task": {"title": title, "description": description, "priority": priority},
            "note": "Gumloop not configured — task saved locally only",
        }

    try:
        output = _gumloop_client.run_flow(
            flow_id="email-to-task",
            inputs={
                "task_title": title,
                "task_description": description,
                "priority": priority,
                "source_email": source_email,
            }
        )
        logger.info(f"Gumloop task workflow triggered: {title}")
        return {"status": "success", "output": output}
    except Exception as e:
        logger.error(f"Gumloop task workflow failed: {e}")
        return {"status": "failed", "error": str(e)}


async def trigger_notification(channel: str, message: str, urgency: str = "normal") -> dict:
    """Trigger a Gumloop notification workflow (Slack, email, etc.)."""
    if not _gumloop_client:
        logger.info(f"Gumloop not configured — notification logged: {message[:100]}")
        return {"status": "local_only", "note": "Gumloop not configured"}

    try:
        output = _gumloop_client.run_flow(
            flow_id="send-notification",
            inputs={
                "channel": channel,
                "message": message,
                "urgency": urgency,
            }
        )
        return {"status": "success", "output": output}
    except Exception as e:
        logger.error(f"Gumloop notification failed: {e}")
        return {"status": "failed", "error": str(e)}


async def trigger_digest_workflow(digest_text: str, recipient: str, emails_count: int) -> dict:
    """Trigger a Gumloop workflow to format and send the daily digest."""
    if not _gumloop_client:
        logger.info("Gumloop not configured — digest sent via AgentMail directly")
        return {"status": "local_only", "note": "Will use AgentMail for digest delivery"}

    try:
        output = _gumloop_client.run_flow(
            flow_id="daily-digest",
            inputs={
                "digest_text": digest_text,
                "recipient": recipient,
                "emails_count": str(emails_count),
            }
        )
        return {"status": "success", "output": output}
    except Exception as e:
        logger.error(f"Gumloop digest workflow failed: {e}")
        return {"status": "failed", "error": str(e)}
