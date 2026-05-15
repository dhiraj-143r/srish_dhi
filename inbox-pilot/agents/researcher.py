"""
InboxPilot — Research Agent
Uses Firecrawl to scrape sender's company website and gather context.
Produces a research summary to help the Drafter write better replies.
"""
import logging
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import EmailState
from tools import firecrawl_tools
from config import config

logger = logging.getLogger("inbox-pilot.agents.researcher")

llm = ChatOpenAI(
    model="gpt-4o",
    api_key=config.OPENAI_API_KEY,
    temperature=0.2,
)


async def researcher_agent(state: EmailState) -> dict:
    """
    Research the sender using Firecrawl web scraping.
    Scrapes sender's company website and generates a research summary.
    """
    log = state.get("processing_log", [])
    sender = state.get("sender", "")

    log.append({"agent": "researcher", "status": "started", "ts": time.time(), "msg": f"🔍 Researching sender: {sender}"})

    # Use Firecrawl to research the sender
    research_data = await firecrawl_tools.research_sender(sender)

    # Scrape any URLs mentioned in the email body
    import re
    body = state.get("body", "")
    urls = re.findall(r'https?://[^\s<>"]+', body)
    if urls:
        log.append({"agent": "researcher", "status": "running", "ts": time.time(), "msg": f"🌐 Scraping {len(urls)} URLs from email body"})
        url_results = await firecrawl_tools.scrape_urls_from_email(urls)
        research_data["email_urls"] = url_results

    # Generate research summary using LLM
    research_summary = ""
    if research_data.get("company_info") or research_data.get("email_urls"):
        try:
            summary_prompt = f"""Based on the following research data about an email sender, write a brief 2-3 sentence summary that would help draft a contextual reply.

Sender: {sender}
Research findings: {str(research_data)[:3000]}

Focus on: Who they are, what their company does, and any relevant context for responding to their email."""

            response = await llm.ainvoke([
                SystemMessage(content="You are a research analyst. Summarize findings concisely."),
                HumanMessage(content=summary_prompt),
            ])
            research_summary = response.content
        except Exception as e:
            logger.warning(f"Research summary generation failed: {e}")
            research_summary = f"Sender domain: {research_data.get('domain', 'unknown')}. {'; '.join(research_data.get('findings', []))}"
    else:
        research_summary = f"No company website found for sender: {sender}. {'; '.join(research_data.get('findings', []))}"

    log.append({
        "agent": "researcher",
        "status": "completed",
        "ts": time.time(),
        "msg": f"✅ Research complete: {research_summary[:100]}..."
    })

    return {
        "research_data": research_data,
        "research_summary": research_summary,
        "processing_log": log,
    }
