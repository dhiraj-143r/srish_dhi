"""
InboxPilot — Main FastAPI Application
Webhook receiver, REST API, WebSocket live feed, and dashboard server.
"""
import logging
import time
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database.db import (
    init_db, get_all_processed_emails, get_email_stats,
    get_agent_logs_for_email,
)
from tools import agentmail_tools
from agents.graph import pipeline
from agents.summarizer import summarizer_agent

# ─── Logging Setup ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("inbox-pilot")

# ─── WebSocket Connection Manager ─────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.active_connections.remove(conn)

ws_manager = ConnectionManager()

# ─── Scheduler ─────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()
_inbox_info: dict = {}

# ─── Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 InboxPilot starting up...")
    
    # Validate config
    missing = config.validate()
    if missing:
        logger.warning(f"⚠️ Missing API keys: {missing}")
    
    # Init database
    await init_db()
    logger.info("✅ Database initialized")
    
    # Create AgentMail inbox
    try:
        inbox = await agentmail_tools.get_or_create_inbox()
        _inbox_info.update(inbox)
        logger.info(f"📬 Agent inbox: {inbox['email_address']}")
    except Exception as e:
        logger.error(f"❌ Failed to create inbox: {e}")
    
    # Start digest scheduler (every 6 hours)
    scheduler.add_job(
        run_digest,
        'interval',
        hours=6,
        id='digest_job',
        next_run_time=None,  # Don't run immediately
    )
    scheduler.start()
    logger.info("⏰ Digest scheduler started (every 6 hours)")
    
    logger.info("=" * 50)
    logger.info(f"📬 Send emails to: {_inbox_info.get('email_address', 'N/A')}")
    logger.info(f"🖥️  Dashboard: http://localhost:{config.PORT}")
    logger.info("=" * 50)
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    logger.info("InboxPilot shut down")


async def run_digest():
    """Run the summarizer agent as a scheduled job."""
    inbox_id = _inbox_info.get("inbox_id")
    await summarizer_agent(inbox_id=inbox_id)


# ─── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(
    title="InboxPilot",
    description="Autonomous Multi-Agent Email Operations Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Dashboard Static Files ───────────────────────────────────────
app.mount("/static", StaticFiles(directory="dashboard"), name="static")


# ─── Webhook Endpoint ─────────────────────────────────────────────
@app.post("/webhook/email")
async def email_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    AgentMail webhook receiver.
    Returns 200 immediately, processes email in background.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    
    logger.info(f"📨 Webhook received: {json.dumps(payload, default=str)[:200]}")
    
    # Broadcast webhook receipt to dashboard
    await ws_manager.broadcast({
        "type": "webhook_received",
        "timestamp": time.time(),
        "preview": str(payload)[:200],
    })
    
    # Process in background
    background_tasks.add_task(process_email, payload)
    
    return {"status": "accepted", "message": "Email queued for processing"}


async def process_email(payload: dict):
    """Process an email through the full LangGraph pipeline."""
    start_time = time.time()
    
    # Extract IDs from different possible payload formats
    # AgentMail sends: {"event_type": "message.received", "message": {"message_id": "...", "inbox_id": "..."}}
    data = payload.get("message", payload.get("data", payload))
    inbox_id = data.get("inbox_id", _inbox_info.get("inbox_id", ""))
    message_id = data.get("message_id", data.get("id", ""))
    
    # Log the extraction for debugging
    logger.info(f"Payload keys: {list(payload.keys())}, extracted message_id: {message_id}, inbox_id: {inbox_id}")
    
    if not message_id:
        logger.warning("No message_id in webhook payload, skipping")
        return

    logger.info(f"⚙️ Processing email: {message_id}")
    
    # Broadcast processing start
    await ws_manager.broadcast({
        "type": "processing_started",
        "message_id": message_id,
        "timestamp": start_time,
    })
    
    # Run the pipeline
    try:
        initial_state = {
            "raw_payload": payload,
            "inbox_id": inbox_id,
            "message_id": message_id,
            "processing_log": [],
            "start_time": start_time,
        }
        
        result = await pipeline.ainvoke(initial_state)
        
        # Broadcast completion
        await ws_manager.broadcast({
            "type": "processing_completed",
            "message_id": message_id,
            "sender": result.get("sender", ""),
            "subject": result.get("subject", ""),
            "urgency": result.get("urgency", ""),
            "category": result.get("category", ""),
            "action_type": result.get("action_type", ""),
            "action_status": result.get("action_status", ""),
            "triage_reasoning": result.get("triage_reasoning", ""),
            "draft_reply": result.get("draft_reply", "")[:200],
            "processing_time_ms": (time.time() - start_time) * 1000,
            "processing_log": result.get("processing_log", []),
            "timestamp": time.time(),
        })
        
        logger.info(f"✅ Email processed: {result.get('action_type', 'unknown')} for {result.get('sender', 'unknown')}")
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed for {message_id}: {e}")
        await ws_manager.broadcast({
            "type": "processing_failed",
            "message_id": message_id,
            "error": str(e),
            "timestamp": time.time(),
        })


# ─── REST API ──────────────────────────────────────────────────────
@app.get("/api/emails")
async def list_emails():
    """Get all processed emails."""
    emails = await get_all_processed_emails()
    return {
        "emails": [
            {
                "id": e.id,
                "message_id": e.message_id,
                "sender": e.sender,
                "subject": e.subject,
                "urgency": e.urgency,
                "category": e.category,
                "action_type": e.action_type,
                "action_status": e.action_status,
                "triage_reasoning": e.triage_reasoning,
                "draft_reply": e.draft_reply,
                "research_summary": e.research_summary,
                "attachment_analysis": e.attachment_analysis,
                "processing_time_ms": e.processing_time_ms,
                "created_at": str(e.created_at),
            }
            for e in emails
        ]
    }


@app.get("/api/stats")
async def get_stats():
    """Get processing statistics."""
    stats = await get_email_stats()
    stats["inbox_email"] = _inbox_info.get("email_address", "N/A")
    stats["inbox_id"] = _inbox_info.get("inbox_id", "N/A")
    return stats


@app.get("/api/email/{message_id}/logs")
async def get_email_logs(message_id: str):
    """Get agent execution logs for a specific email."""
    logs = await get_agent_logs_for_email(message_id)
    return {"logs": [{"agent": l.agent_name, "status": l.status, "output": l.output_summary, "duration_ms": l.duration_ms} for l in logs]}


@app.post("/api/webhook/register")
async def register_webhook_endpoint(request: Request):
    """Register a webhook URL with AgentMail."""
    body = await request.json()
    url = body.get("url", "")
    if not url:
        return {"error": "URL required"}
    result = await agentmail_tools.register_webhook(url)
    return result


@app.post("/api/digest/trigger")
async def trigger_digest():
    """Manually trigger the digest generation."""
    result = await summarizer_agent(inbox_id=_inbox_info.get("inbox_id"))
    return result


@app.get("/health")
async def health_check():
    """Health check — verifies all integrations."""
    checks = {
        "agentmail": bool(config.AGENTMAIL_API_KEY),
        "firecrawl": bool(config.FIRECRAWL_API_KEY),
        "roboflow": bool(config.ROBOFLOW_API_KEY),
        "openai": bool(config.OPENAI_API_KEY),
        "gumloop": config.has_gumloop(),
        "omium": config.has_omium(),
        "inbox": _inbox_info.get("email_address", None),
    }
    return {"status": "healthy", "checks": checks}


# ─── WebSocket ─────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ─── Dashboard ─────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard."""
    return FileResponse("dashboard/index.html")


# ─── Run ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
