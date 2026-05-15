"""
InboxPilot — Database Setup & Queries
Async SQLite database with SQLAlchemy for email processing history.
"""
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from database.models import Base, ProcessedEmail, AgentLog, DailyDigest
from config import config

engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get a database session."""
    async with async_session() as session:
        return session


# ─── Processed Emails ─────────────────────────────────────────────

async def save_processed_email(data: dict) -> ProcessedEmail:
    """Save a processed email record."""
    async with async_session() as session:
        email = ProcessedEmail(**data)
        session.add(email)
        await session.commit()
        await session.refresh(email)
        return email


async def update_processed_email(message_id: str, updates: dict):
    """Update a processed email record by message_id."""
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedEmail).where(ProcessedEmail.message_id == message_id)
        )
        email = result.scalar_one_or_none()
        if email:
            for key, value in updates.items():
                setattr(email, key, value)
            await session.commit()


async def get_processed_email(message_id: str) -> ProcessedEmail | None:
    """Get a processed email by message_id."""
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedEmail).where(ProcessedEmail.message_id == message_id)
        )
        return result.scalar_one_or_none()


async def get_all_processed_emails(limit: int = 50) -> list[ProcessedEmail]:
    """Get recent processed emails ordered by newest first."""
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedEmail)
            .order_by(ProcessedEmail.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_email_stats() -> dict:
    """Get processing statistics."""
    async with async_session() as session:
        total = await session.execute(select(func.count(ProcessedEmail.id)))
        urgent = await session.execute(
            select(func.count(ProcessedEmail.id)).where(ProcessedEmail.urgency == "high")
        )
        replied = await session.execute(
            select(func.count(ProcessedEmail.id)).where(ProcessedEmail.action_type == "reply")
        )
        tasks = await session.execute(
            select(func.count(ProcessedEmail.id)).where(ProcessedEmail.action_type == "create_task")
        )
        archived = await session.execute(
            select(func.count(ProcessedEmail.id)).where(ProcessedEmail.action_type == "archive")
        )
        return {
            "total_processed": total.scalar() or 0,
            "urgent_count": urgent.scalar() or 0,
            "auto_replied": replied.scalar() or 0,
            "tasks_created": tasks.scalar() or 0,
            "archived": archived.scalar() or 0,
        }


# ─── Agent Logs ───────────────────────────────────────────────────

async def save_agent_log(data: dict) -> AgentLog:
    """Save an agent execution log."""
    async with async_session() as session:
        log = AgentLog(**data)
        session.add(log)
        await session.commit()
        return log


async def get_agent_logs_for_email(email_id: str) -> list[AgentLog]:
    """Get all agent logs for a specific email processing run."""
    async with async_session() as session:
        result = await session.execute(
            select(AgentLog)
            .where(AgentLog.email_id == email_id)
            .order_by(AgentLog.created_at.asc())
        )
        return list(result.scalars().all())


# ─── Daily Digest ─────────────────────────────────────────────────

async def get_emails_since(since: datetime.datetime) -> list[ProcessedEmail]:
    """Get all emails processed since a given time."""
    async with async_session() as session:
        result = await session.execute(
            select(ProcessedEmail)
            .where(ProcessedEmail.created_at >= since)
            .order_by(ProcessedEmail.created_at.asc())
        )
        return list(result.scalars().all())


async def save_digest(data: dict) -> DailyDigest:
    """Save a daily digest record."""
    async with async_session() as session:
        digest = DailyDigest(**data)
        session.add(digest)
        await session.commit()
        return digest
