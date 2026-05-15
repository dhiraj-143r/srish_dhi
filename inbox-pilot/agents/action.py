"""
InboxPilot — Action Agent
Executes the final decided action: send reply, create task, archive, etc.
Produces real side-effects via AgentMail and Gumloop.
"""
import logging
import time
from agents.state import EmailState
from tools import agentmail_tools, gumloop_tools
from database.db import save_processed_email, save_agent_log

logger = logging.getLogger("inbox-pilot.agents.action")

# Omium tracing (optional)
try:
    import omium
    _trace = omium.trace(name="action_agent", span_type="agent")
except ImportError:
    _trace = lambda f: f


@_trace
async def action_agent(state: EmailState) -> dict:
    """Execute the decided action based on triage results."""
    log = state.get("processing_log", [])
    action_type = state.get("action_type", "reply")
    
    log.append({"agent": "action", "status": "started", "ts": time.time(), "msg": f"⚡ Executing action: {action_type}"})

    action_result = {}
    action_status = "completed"

    try:
        if action_type == "reply" and state.get("draft_reply"):
            # Send the drafted reply via AgentMail
            result = await agentmail_tools.send_reply(
                inbox_id=state.get("inbox_id", ""),
                to=state.get("sender", ""),
                subject=state.get("draft_subject", f"Re: {state.get('subject', '')}"),
                body=state.get("draft_reply", ""),
                thread_id=state.get("thread_id"),
            )
            action_result = {"type": "reply_sent", "details": result}
            log.append({"agent": "action", "status": "completed", "ts": time.time(),
                        "msg": f"📧 Reply sent to {state.get('sender', '')}"})

        elif action_type == "create_task":
            # Create a task via Gumloop (or locally)
            task_result = await gumloop_tools.trigger_task_workflow(
                title=f"[Email] {state.get('subject', 'New Task')}",
                description=f"From: {state.get('sender', '')}\n\n{state.get('body', '')[:500]}",
                priority=state.get("urgency", "medium"),
                source_email=state.get("sender", ""),
            )
            action_result = {"type": "task_created", "details": task_result}
            
            # Also send acknowledgment reply if there's a draft
            if state.get("draft_reply"):
                await agentmail_tools.send_reply(
                    inbox_id=state.get("inbox_id", ""),
                    to=state.get("sender", ""),
                    subject=state.get("draft_subject", f"Re: {state.get('subject', '')}"),
                    body=state.get("draft_reply", ""),
                    thread_id=state.get("thread_id"),
                )
            log.append({"agent": "action", "status": "completed", "ts": time.time(),
                        "msg": f"📋 Task created: {state.get('subject', '')[:50]}"})

        elif action_type == "archive":
            action_result = {"type": "archived", "details": {"message_id": state.get("message_id")}}
            log.append({"agent": "action", "status": "completed", "ts": time.time(),
                        "msg": "📁 Email archived (no action needed)"})

        elif action_type == "escalate":
            # Send urgent notification
            await gumloop_tools.trigger_notification(
                channel="critical",
                message=f"🚨 ESCALATED: {state.get('subject', '')} from {state.get('sender', '')}",
                urgency="critical",
            )
            # Send auto-reply acknowledging the emergency
            if state.get("draft_reply"):
                await agentmail_tools.send_reply(
                    inbox_id=state.get("inbox_id", ""),
                    to=state.get("sender", ""),
                    subject=state.get("draft_subject", f"Re: {state.get('subject', '')}"),
                    body=state.get("draft_reply", ""),
                    thread_id=state.get("thread_id"),
                )
            action_result = {"type": "escalated", "details": {"message_id": state.get("message_id"), "notification": "sent"}}
            log.append({"agent": "action", "status": "completed", "ts": time.time(),
                        "msg": f"🚨 ESCALATED to leadership: {state.get('subject', '')[:50]}"})

        else:
            action_result = {"type": action_type, "details": {"note": "Action type not implemented"}}
            log.append({"agent": "action", "status": "completed", "ts": time.time(),
                        "msg": f"ℹ️ Action '{action_type}' completed"})

        # Notify via Gumloop if urgent
        if state.get("urgency") == "high":
            await gumloop_tools.trigger_notification(
                channel="urgent",
                message=f"🔴 URGENT email from {state.get('sender', '')}: {state.get('subject', '')}",
                urgency="high",
            )

    except Exception as e:
        logger.error(f"Action execution failed: {e}")
        action_status = "failed"
        action_result = {"type": action_type, "error": str(e)}
        log.append({"agent": "action", "status": "failed", "ts": time.time(), "msg": f"❌ Action failed: {e}"})

    # Save to database
    try:
        end_time = time.time()
        start_time = state.get("start_time", end_time)
        
        await save_processed_email({
            "message_id": state.get("message_id", ""),
            "inbox_id": state.get("inbox_id", ""),
            "thread_id": state.get("thread_id", ""),
            "sender": state.get("sender", ""),
            "subject": state.get("subject", ""),
            "body_preview": state.get("body", "")[:200],
            "has_attachments": 1 if state.get("has_attachments") else 0,
            "urgency": state.get("urgency", ""),
            "category": state.get("category", ""),
            "action_type": action_type,
            "triage_reasoning": state.get("triage_reasoning", ""),
            "research_summary": state.get("research_summary", ""),
            "attachment_analysis": state.get("attachment_summary", ""),
            "action_result": str(action_result),
            "draft_reply": state.get("draft_reply", ""),
            "action_status": action_status,
            "processing_time_ms": (end_time - start_time) * 1000,
        })
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")

    return {
        "action_result": action_result,
        "action_status": action_status,
        "end_time": time.time(),
        "processing_log": log,
    }
