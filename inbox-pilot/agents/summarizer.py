"""
InboxPilot — Summarizer Agent
Generates periodic email digests summarizing all processed emails.
Runs on a cron schedule to prove the long-running requirement.
"""
import logging
import time
import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import EmailState
from tools import agentmail_tools, gumloop_tools
from database.db import get_emails_since, save_digest
from config import config

logger = logging.getLogger("inbox-pilot.agents.summarizer")

llm = ChatOpenAI(model="gpt-4o", api_key=config.OPENAI_API_KEY, temperature=0.3)


async def summarizer_agent(inbox_id: str = None):
    """Generate a digest of recent emails. Called by scheduler, not by main pipeline."""
    logger.info("📊 Summarizer Agent started — generating digest...")
    
    since = datetime.datetime.utcnow() - datetime.timedelta(hours=6)
    emails = await get_emails_since(since)
    
    if not emails:
        logger.info("No emails to summarize in the last 6 hours")
        return {"status": "skipped", "reason": "no emails"}

    # Build email summary for LLM
    email_summaries = []
    for e in emails:
        email_summaries.append(
            f"- [{e.urgency}] From: {e.sender} | Subject: {e.subject} | "
            f"Action: {e.action_type} | Status: {e.action_status}"
        )
    
    email_list = "\n".join(email_summaries)
    
    try:
        response = await llm.ainvoke([
            SystemMessage(content="You are an executive assistant. Write a concise email digest summary."),
            HumanMessage(content=f"""Generate a brief email digest for the last 6 hours.

Emails processed ({len(emails)} total):
{email_list}

Format as a clean summary with:
1. Quick stats (total, urgent, replied, archived)
2. Key highlights (most important emails)
3. Action items still pending (if any)

Keep it under 300 words."""),
        ])
        
        digest_text = response.content
        
        # Save digest to DB
        await save_digest({
            "summary_text": digest_text,
            "emails_count": len(emails),
            "period_start": since,
            "period_end": datetime.datetime.utcnow(),
        })
        
        # Send digest via AgentMail if inbox available
        if inbox_id:
            try:
                inbox = await agentmail_tools.get_or_create_inbox()
                await agentmail_tools.send_reply(
                    inbox_id=inbox["inbox_id"],
                    to=inbox["email_address"],  # Send to self for demo
                    subject=f"📊 InboxPilot Digest — {datetime.datetime.now().strftime('%b %d, %H:%M')}",
                    body=digest_text,
                )
                logger.info("Digest email sent")
            except Exception as e:
                logger.warning(f"Could not send digest email: {e}")
        
        # Try Gumloop for enhanced distribution
        await gumloop_tools.trigger_digest_workflow(
            digest_text=digest_text,
            recipient="team",
            emails_count=len(emails),
        )
        
        logger.info(f"📊 Digest generated: {len(emails)} emails summarized")
        return {"status": "completed", "emails_count": len(emails), "digest": digest_text}
        
    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        return {"status": "failed", "error": str(e)}
