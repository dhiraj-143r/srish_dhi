# 📬 InboxPilot — Autonomous Multi-Agent Email Operations

> An end-to-end autonomous email pipeline that triages, researches, analyzes attachments, drafts replies, and takes action — with zero human intervention.

## 🏗️ Architecture

```
AgentMail Webhook → FastAPI → LangGraph Pipeline
                                 ├── Watcher Agent (parse email)
                                 ├── Triage Agent (GPT-4o classification)
                                 ├── Research Agent (Firecrawl web scraping)
                                 ├── Vision Agent (Roboflow image analysis)
                                 ├── Drafter Agent (GPT-4o reply generation)
                                 ├── Action Agent (execute: send, create task, archive)
                                 └── Summarizer Agent (scheduled digest)
```

## 🚀 Quickstart

```bash
# 1. Clone & enter
cd inbox-pilot

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys
cp .env.example .env
# Edit .env with your API keys

# 5. Run
python main.py
```

The dashboard is available at `http://localhost:8000`

## 🔗 Webhook Setup

1. Install ngrok: `brew install ngrok`
2. Start ngrok: `ngrok http 8000`
3. Copy the HTTPS URL
4. Register webhook via dashboard or API:
   ```bash
   curl -X POST http://localhost:8000/api/webhook/register \
     -H "Content-Type: application/json" \
     -d '{"url": "https://YOUR-NGROK-URL/webhook/email"}'
   ```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph |
| LLM | OpenAI GPT-4o |
| Backend | FastAPI + Uvicorn |
| Email | AgentMail |
| Web Scraping | Firecrawl |
| Computer Vision | Roboflow |
| Workflow Automation | Gumloop |
| Database | SQLite + SQLAlchemy |
| Tracing | Omium SDK |
| Dashboard | Vanilla HTML/CSS/JS + WebSocket |

## 📊 Agents

1. **Watcher** — Parses incoming email from AgentMail webhook
2. **Triage** — GPT-4o classifies urgency, category, and action with chain-of-thought reasoning
3. **Research** — Firecrawl scrapes sender's company website for context
4. **Vision** — Roboflow analyzes image attachments (invoices, receipts, etc.)
5. **Drafter** — GPT-4o generates contextual, tone-appropriate replies
6. **Action** — Executes: send reply, create task, archive email
7. **Summarizer** — Generates periodic email digests (cron-scheduled)

## 📝 License

MIT
