"""
InboxPilot — Drafter Agent
LLM-powered reply generation using triage, research, and vision context.
"""
import logging
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import EmailState
from config import config

logger = logging.getLogger("inbox-pilot.agents.drafter")

llm = ChatOpenAI(model="gpt-4o", api_key=config.OPENAI_API_KEY, temperature=0.4)

SYSTEM_PROMPT = """You are a professional email reply drafter. Write contextual, helpful replies.
- Match tone to urgency: urgent=concise, medium=professional, low=friendly
- Reference research data naturally if available
- Acknowledge attachments if analyzed
- Keep replies 3-6 sentences
- Sign off as "InboxPilot AI Assistant"
Respond with ONLY the reply body text."""


async def drafter_agent(state: EmailState) -> dict:
    """Generate a contextual email reply using GPT-4o."""
    log = state.get("processing_log", [])
    
    if state.get("action_type") == "archive":
        log.append({"agent": "drafter", "status": "skipped", "ts": time.time(), "msg": "✍️ Skipped — archive action"})
        return {"draft_reply": "", "draft_subject": "", "processing_log": log}

    log.append({"agent": "drafter", "status": "started", "ts": time.time(), "msg": "✍️ Drafting reply..."})

    context = f"""ORIGINAL EMAIL:
From: {state.get('sender', 'unknown')}
Subject: {state.get('subject', '')}
Body: {state.get('body', '')[:2000]}

TRIAGE: urgency={state.get('urgency','medium')}, category={state.get('category','general')}, action={state.get('action_type','reply')}
Reasoning: {state.get('triage_reasoning', 'N/A')}
Research: {state.get('research_summary', 'None')}
Attachments: {state.get('attachment_summary', 'None')}
Thread depth: {len(state.get('thread_messages', []))} previous messages"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Draft a reply:\n\n{context}"),
        ])
        draft = response.content.strip()
        subj = state.get("subject", "")
        reply_subject = f"Re: {subj}" if not subj.startswith("Re:") else subj

        log.append({"agent": "drafter", "status": "completed", "ts": time.time(), "msg": f"✅ Draft: {len(draft)} chars"})
        return {"draft_reply": draft, "draft_subject": reply_subject, "processing_log": log}
    except Exception as e:
        logger.error(f"Draft failed: {e}")
        log.append({"agent": "drafter", "status": "failed", "ts": time.time(), "msg": f"❌ Error: {e}"})
        return {
            "draft_reply": "Thank you for your email. I've received it and will review shortly.\n\nBest,\nInboxPilot AI",
            "draft_subject": f"Re: {state.get('subject', '')}",
            "processing_log": log,
        }
