"""
InboxPilot — Shared Agent State
TypedDict defining the state that flows through the LangGraph pipeline.
Every agent reads from and writes to this shared state.
"""
from typing import TypedDict, Optional, Any


class EmailState(TypedDict, total=False):
    """Shared state for the email processing pipeline."""

    # ─── Input (from webhook) ──────────────────────────────
    raw_payload: dict                  # Raw webhook payload
    inbox_id: str                      # AgentMail inbox ID
    message_id: str                    # AgentMail message ID

    # ─── Watcher Agent Output ──────────────────────────────
    sender: str                        # Sender email address
    subject: str                       # Email subject line
    body: str                          # Email body text
    html_body: str                     # Email HTML body
    thread_id: str                     # Thread ID for context
    thread_messages: list              # Previous messages in thread
    attachments: list                  # List of attachment objects
    has_attachments: bool              # Quick flag
    received_at: str                   # Timestamp

    # ─── Triage Agent Output ───────────────────────────────
    urgency: str                       # high | medium | low
    category: str                      # meeting_request | task | question | newsletter | spam | important
    action_type: str                   # reply | create_task | archive | forward
    needs_research: bool               # Should Research Agent run?
    triage_reasoning: str              # Step-by-step chain-of-thought

    # ─── Research Agent Output ─────────────────────────────
    research_data: dict                # Sender/company info from Firecrawl
    research_summary: str              # LLM-generated summary of research

    # ─── Vision Agent Output ───────────────────────────────
    attachment_analysis: list          # Roboflow classification results
    attachment_summary: str            # Summary of what attachments contain

    # ─── Drafter Agent Output ──────────────────────────────
    draft_reply: str                   # Generated reply text
    draft_subject: str                 # Reply subject line

    # ─── Action Agent Output ───────────────────────────────
    action_result: dict                # Result of the executed action
    action_status: str                 # completed | failed

    # ─── Pipeline Metadata ─────────────────────────────────
    processing_log: list               # List of log messages for dashboard
    error: Optional[str]               # Error message if pipeline fails
    start_time: float                  # Pipeline start timestamp
    end_time: float                    # Pipeline end timestamp
