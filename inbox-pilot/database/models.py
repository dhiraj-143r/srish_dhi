"""
InboxPilot — Database Models
SQLAlchemy models for persisting email processing history and agent logs.
"""
import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ProcessedEmail(Base):
    """Record of every email processed by the pipeline."""
    __tablename__ = "processed_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    inbox_id = Column(String(255), nullable=False)
    thread_id = Column(String(255), nullable=True)

    # Email content
    sender = Column(String(255), nullable=False)
    subject = Column(Text, nullable=True)
    body_preview = Column(Text, nullable=True)
    has_attachments = Column(Integer, default=0)  # SQLite boolean

    # Triage results
    urgency = Column(String(20), nullable=True)  # high, medium, low
    category = Column(String(50), nullable=True)  # meeting, task, question, etc.
    action_type = Column(String(50), nullable=True)  # reply, create_task, archive
    triage_reasoning = Column(Text, nullable=True)  # Chain-of-thought

    # Research & Vision results
    research_summary = Column(Text, nullable=True)
    attachment_analysis = Column(Text, nullable=True)

    # Action taken
    action_result = Column(Text, nullable=True)
    draft_reply = Column(Text, nullable=True)
    action_status = Column(String(20), default="pending")  # pending, completed, failed

    # Metadata
    processing_time_ms = Column(Float, nullable=True)
    omium_trace_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AgentLog(Base):
    """Log of individual agent executions within a pipeline run."""
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String(255), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(20), default="running")  # running, completed, failed
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class DailyDigest(Base):
    """Record of generated daily digest summaries."""
    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    summary_text = Column(Text, nullable=False)
    emails_count = Column(Integer, default=0)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    sent_to = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
