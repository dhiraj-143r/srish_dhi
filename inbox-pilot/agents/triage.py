"""
InboxPilot — Triage Agent
LLM-powered email classification with chain-of-thought reasoning.
Determines urgency, category, required action, and whether research is needed.
"""
import logging
import time
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import EmailState
from config import config

logger = logging.getLogger("inbox-pilot.agents.triage")

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o",
    api_key=config.OPENAI_API_KEY,
    temperature=0.1,
    model_kwargs={"response_format": {"type": "json_object"}},
)

TRIAGE_SYSTEM_PROMPT = """You are an expert email triage assistant. Analyze the incoming email and classify it.

You MUST respond with a JSON object containing exactly these fields:

{
    "urgency": "high" | "medium" | "low",
    "category": "meeting_request" | "task" | "question" | "important" | "newsletter" | "spam" | "introduction" | "follow_up",
    "action_type": "reply" | "create_task" | "archive" | "escalate" | "forward",
    "needs_research": true | false,
    "reasoning": "Your step-by-step reasoning for this classification..."
}

Classification rules:
- URGENCY: "high" = needs response within hours (deadlines, urgent requests, boss/client emails). "medium" = needs response within a day. "low" = informational, no response needed.
- CATEGORY: Choose the most fitting category based on email content and intent.
- ACTION: "reply" = draft and send a response. "create_task" = extract action items and send acknowledgment. "archive" = no action needed, just file. "escalate" = CRITICAL situations requiring immediate human intervention (security breaches, data leaks, legal threats, system-wide outages, executive-level emergencies). Use escalate ONLY for genuinely critical emergencies, not for normal urgent emails. "forward" = needs to be forwarded to someone else.
- NEEDS_RESEARCH: Set to true if understanding the sender's company/background would help craft a better response. Usually true for unknown senders, partnership inquiries, or business proposals.
- REASONING: Explain your classification step-by-step. This is critical for transparency. Include what signals you used (keywords, sender, tone, etc.).
"""

# Omium tracing (optional)
try:
    import omium
    _trace = omium.trace(name="triage_agent", span_type="agent")
except ImportError:
    _trace = lambda f: f


@_trace
async def triage_agent(state: EmailState) -> dict:
    """
    Classify the email using GPT-4o with structured output.
    Returns urgency, category, action type, and chain-of-thought reasoning.
    """
    log = state.get("processing_log", [])
    log.append({"agent": "triage", "status": "started", "ts": time.time(), "msg": "🧠 Analyzing email content..."})

    sender = state.get("sender", "unknown")
    subject = state.get("subject", "")
    body = state.get("body", "")[:2000]  # Truncate to avoid token limits
    has_attachments = state.get("has_attachments", False)
    thread_count = len(state.get("thread_messages", []))

    # Build the email context for the LLM
    email_context = f"""
SENDER: {sender}
SUBJECT: {subject}
BODY:
{body}

METADATA:
- Has attachments: {has_attachments}
- Thread depth: {thread_count} previous messages
- Attachment count: {len(state.get('attachments', []))}
"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=f"Classify this email:\n\n{email_context}"),
        ])

        # Parse JSON response
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            content = response.content
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
            else:
                raise ValueError("Could not parse LLM response as JSON")

        urgency = result.get("urgency", "medium")
        category = result.get("category", "important")
        action_type = result.get("action_type", "reply")
        needs_research = result.get("needs_research", False)
        reasoning = result.get("reasoning", "No reasoning provided")

        urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(urgency, "⚪")

        log.append({
            "agent": "triage",
            "status": "completed",
            "ts": time.time(),
            "msg": f"{urgency_emoji} Triage: urgency={urgency}, category={category}, action={action_type}"
        })

        return {
            "urgency": urgency,
            "category": category,
            "action_type": action_type,
            "needs_research": needs_research,
            "triage_reasoning": reasoning,
            "processing_log": log,
        }

    except Exception as e:
        logger.error(f"Triage failed: {e}")
        log.append({"agent": "triage", "status": "failed", "ts": time.time(), "msg": f"❌ Triage error: {str(e)}"})
        # Fallback defaults
        return {
            "urgency": "medium",
            "category": "important",
            "action_type": "reply",
            "needs_research": False,
            "triage_reasoning": f"Triage failed with error: {str(e)}. Defaulting to medium urgency.",
            "processing_log": log,
            "error": str(e),
        }
