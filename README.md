# 🧠 Personalized DSA Coach Agent

> A fully agentic, AI-powered DSA coaching system that assigns daily problems, gives progressive hints, validates your pattern notes, tracks your progress, and sends Telegram reminders at 6 PM every day — whether your laptop is on or not.

**Status: Fully deployed and working on Railway** ✅

---

## Why I Built This

I kept starting DSA prep and stopping. Open Striver's sheet → do arrays for 3 days → quit. Never touched DP, Trees, or Heaps properly. The real problem wasn't motivation — it was:

- No accountability system
- Googling full solutions immediately (learning nothing)
- No memory of past mistakes, so same patterns tripped me up repeatedly
- No dynamic adjustment — sheets treat everyone the same

So I built a coach that:
- Knows exactly where I am in my learning journey
- Won't let me cheat my way through (notes are validated by AI before a problem counts)
- Remembers every pattern I struggled with (ChromaDB RAG)
- Adjusts difficulty automatically based on my clean-solve rate
- Sends a Telegram message at 6 PM every day whether my laptop is open or not

---

## What This Project Does

```
You solve on LeetCode
    ↓
Log it in the UI (2 min)
    ↓
Write pattern notes → AI validates them → stored in ChromaDB
    ↓
Next time you ask for a hint on a similar problem →
coach pulls YOUR OWN past notes and calls out your blind spots
    ↓
6 PM every day → Telegram message with today's specific problems
based on your current phase, difficulty level, and streak
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API | FastAPI + Python 3.11 | Async, fast, clean |
| Agent | LangGraph + LangChain | Stateful agent with tool-calling |
| LLM (local) | Ollama + llama2 | Free, runs on laptop for local dev |
| LLM (cloud) | Groq (llama3-70b-8192) | Free API, auto-selected on Railway |
| Database | PostgreSQL + SQLAlchemy | Progress, streaks, notes |
| Vector Store | ChromaDB | Semantic search over your past notes |
| Background Jobs | Celery + Redis | Processes tasks async |
| Notifications | Telegram Bot API | Daily 6 PM assignment to phone |
| Cron Scheduler | GitHub Actions | Triggers nudge at 6 PM IST daily (free) |
| Deployment | Railway | Hosts backend, Postgres, Redis, Celery worker |
| Frontend | Vanilla HTML/CSS/JS | Single file, open directly in browser |

---

## Final Architecture (Production)

```
┌─────────────────────────────────────────────────────────┐
│  Browser (dsa-coach-ui.html — local file on laptop)     │
│  Open this file → it talks to Railway backend via HTTPS │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS API calls
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Railway (Cloud — always running)                       │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐                      │
│  │  FastAPI    │  │ Celery Worker│                      │
│  │  (Serverless│  │ (always on)  │                      │
│  │  mode)      │  │              │                      │
│  └──────┬──────┘  └──────┬───────┘                      │
│         │                │                              │
│  ┌──────▼──────┐  ┌──────▼────────┐                     │
│  │  LangGraph  │  │     Redis     │                     │
│  │  + Groq LLM │  │  (task queue) │                     │
│  └──────┬──────┘  └───────────────┘                     │
│         │                                               │
│  ┌──────▼──────┐  ┌──────────────┐                      │
│  │ PostgreSQL  │  │   ChromaDB   │                      │
│  │ (progress,  │  │ (pattern     │                      │
│  │  streaks)   │  │  notes RAG)  │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
          │
          ▼ GitHub Actions (cron: 6 PM IST daily, FREE)
    POST /api/v1/nudge/trigger
          │
          ▼ Telegram Bot API
   📱 Your Phone — daily problem assignment
```

### Why GitHub Actions instead of Celery Beat?

Celery Beat runs as an always-on service on Railway, costing money 24/7 just to fire one cron job. GitHub Actions runs the same cron for **free** on public repos. So we deleted Celery Beat from Railway and use GitHub Actions instead — same result, zero extra cost.

---

## The 5 Learning Phases

| Phase | Topics | Min Problems | Duration |
|-------|--------|-------------|----------|
| 1 — Foundation | Arrays, Binary Search, Linked Lists | 37 | Weeks 1–3 |
| 2 — Big Unlock | Recursion, Trees & BST, Heaps | 49 | Weeks 4–8 |
| 3 — Graph World | Graphs, Advanced Graphs | 30 | Weeks 9–13 |
| 4 — DP Demystified | DP Foundation, Knapsack, LCS/LIS | 38 | Weeks 14–20 |
| 5 — Interview Mode | Trie, Segment Tree, Random Mixed | 46 | Weeks 21–24 |

**Total: ~200 minimum problems.** In practice 300–400+ as you revisit weak areas.

### Dynamic difficulty
- Clean solve rate > 70% + hint rate < 30% → **Hard**, 3 problems/day
- Clean solve rate > 50% → **Medium**, 2 problems/day
- Below → **Easy**, 1 problem/day

---

## Key Features

### 1. Progressive Hint System (No Cheating)
```
Step 1: Struggle for 30 min
Step 2: Name the pattern → unlocks hint
Step 3: Get a clue (no code)
Step 4: Full solution → must write notes first before problem is logged
```

### 2. Notes Validation (The Strict Coach Guardrail)

**Rejected (score 2/10):** "Used sliding window"

**Approved (score 8/10):** "Pattern: Sliding Window. Applies here because we need max sum of exactly k consecutive elements. Instead of recalculating O(n*k), maintain running sum by subtracting left and adding right — O(n). Recognize next time when: fixed subarray size + need max/min/sum."

Approved notes → stored in ChromaDB → referenced in future hints automatically.

### 3. RAG-Powered Hints
When you ask for a hint, the system searches ChromaDB for problems YOU struggled with that are semantically similar. If you've had trouble with sliding window 3 times before, the coach calls it out.

### 4. Daily Telegram Notification
GitHub Actions fires at 6:00 PM IST daily → hits `/nudge/trigger` → Celery Worker processes it → Groq generates personalised message → Telegram delivers to your phone. Works whether laptop is on or off.

### 5. Dynamic Pacing
The system tracks your clean-solve rate and hint rate per topic. If you're solving cleanly it pushes harder. If you're struggling it slows down. The roadmap adapts to you.

---

## Project Structure

```
dsa-coach-backend/
├── app/
│   ├── main.py                          # FastAPI app factory + lifespan startup
│   ├── config.py                        # All settings via pydantic-settings (.env)
│   ├── api/
│   │   ├── schemas.py                   # Pydantic request/response models
│   │   └── routes/
│   │       ├── chat.py                  # POST /chat → LangGraph agent
│   │       └── routes.py               # /users /progress /problems /notes /hints /nudge
│   ├── agent/
│   │   ├── coach_graph.py               # LangGraph: rag_prefetch → coach → tools loop
│   │   ├── prompts/coach_prompts.py     # All LLM prompts + 5-phase roadmap data
│   │   └── tools/coach_tools.py         # validate_notes, log_problem, query_struggles...
│   ├── db/
│   │   ├── models.py                    # SQLAlchemy: users, topic_progress, solved_problems,
│   │   │                               #   pattern_notes, daily_assignments
│   │   ├── session.py                   # Async engine + session factory
│   │   └── migrations/env.py            # Alembic config
│   ├── services/
│   │   ├── llm.py                       # Auto-switches: Groq (cloud) / Ollama (local)
│   │   ├── vector_store.py              # ChromaDB: upsert + semantic query
│   │   ├── progress_service.py          # All DB operations
│   │   └── telegram_service.py          # Telegram Bot API wrapper
│   └── workers/
│       ├── celery_app.py                # Celery app config
│       └── tasks.py                     # send_nudge_to_user, sync_notes_to_chroma
│
├── .github/workflows/
│   └── daily_nudge.yml                  # GitHub Actions cron: 6 PM IST daily
│
├── tests/
│   ├── unit/test_core.py
│   └── integration/test_api.py
│
├── dsa-coach-ui.html                    # Frontend (single file, open in browser)
├── docker-compose.yml                   # Local dev: Postgres + Redis + ChromaDB
├── Procfile                             # Railway process definitions
├── railway.json                         # Railway build config (no start command)
├── .python-version                      # Forces Python 3.11 on Railway
├── pyproject.toml                       # Dependencies
├── requirements.txt                     # Flat requirements for Railway build
├── start.ps1                            # Windows: one-click local dev startup
└── .env.example                         # Environment variable template
```

---

## Local Development Setup

### Prerequisites
- Python 3.11 specifically (not 3.12/3.13/3.14 — some packages break)
- Docker Desktop (running)
- Ollama installed with llama2: `ollama pull llama2`

### Step 1 — Clone and setup

```bash
git clone https://github.com/MPrasannaTeja/Personalized-DSA-Coach.git
cd Personalized-DSA-Coach

py -3.11 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### Step 2 — Configure .env

```bash
cp .env.example .env
```

Fill in:
```env
GROQ_API_KEY=                   # leave empty to use Ollama locally
OLLAMA_MODEL=llama2
TELEGRAM_BOT_TOKEN=             # from @BotFather on Telegram
TELEGRAM_DEFAULT_CHAT_ID=       # from @userinfobot on Telegram
APP_SECRET_KEY=                 # python -c "import secrets; print(secrets.token_hex(32))"
DATABASE_URL=postgresql+asyncpg://dsa_coach:changeme@localhost:5432/dsa_coach
DATABASE_URL_SYNC=postgresql://dsa_coach:changeme@localhost:5432/dsa_coach
REDIS_URL=redis://localhost:6379/0
```

### Step 3 — Start infrastructure

```bash
docker-compose up -d
docker-compose ps   # all 3 should show "healthy"
```

### Step 4 — Start everything

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Opens 3 terminals: FastAPI on `localhost:8000`, Celery Worker, Celery Beat.

### Step 5 — Create your user

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/users" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username": "yourname", "telegram_chat_id": "YOUR_TELEGRAM_ID"}' `
  -UseBasicParsing
```

Save the `id` from the response.

### Step 6 — Open the UI

Open `dsa-coach-ui.html` in browser. Change the API URL at the top of the script section from the Railway URL back to `http://localhost:8000/api/v1`. Paste your user ID → Enter.

---

## Cloud Deployment (Railway)

### Services on Railway
| Service | Type | Start Command |
|---------|------|--------------|
| Personalized-DSA-Coach | Web (Serverless) | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| celery | Worker | `celery -A app.workers.celery_app worker --loglevel=info --pool=solo` |
| PostgreSQL | Database addon | auto |
| Redis | Database addon | auto |

**Note: Celery Beat is NOT deployed on Railway.** The daily cron is handled by GitHub Actions (free) instead.

### Step 1 — Railway setup

1. Go to [railway.app](https://railway.app) → sign in with GitHub
2. New Project → Deploy from GitHub repo
3. Add PostgreSQL addon → Add Redis addon
4. Add a second service from same repo → set start command to celery worker command above

### Step 2 — Environment variables (main service + celery worker)

```
APP_ENV                   = development
APP_SECRET_KEY            = your_secret
GROQ_API_KEY              = gsk_... (from console.groq.com — free)
TELEGRAM_BOT_TOKEN        = your_bot_token
TELEGRAM_DEFAULT_CHAT_ID  = your_chat_id
DATABASE_URL              = postgresql+asyncpg://... (Railway auto-fills)
DATABASE_URL_SYNC         = postgresql://... (same but no +asyncpg)
REDIS_URL                 = redis://... (Railway auto-fills)
CELERY_BROKER_URL         = same as REDIS_URL
CELERY_RESULT_BACKEND     = same as REDIS_URL (change /0 to /1)
CORS_ORIGINS              = ["null","https://your-service.up.railway.app"]
CHROMA_HOST               = localhost
CHROMA_PORT               = 8001
CHROMA_COLLECTION_NAME    = dsa_pattern_notes
DAILY_NUDGE_HOUR          = 18
DAILY_NUDGE_MINUTE        = 0
DAILY_NUDGE_TIMEZONE      = Asia/Kolkata
```

### Step 3 — GitHub Actions secrets

GitHub repo → Settings → Secrets and variables → Actions → New secret:

| Secret | Value |
|--------|-------|
| `RAILWAY_API_URL` | `https://your-service.up.railway.app` |
| `USER_ID` | your Railway user UUID |

### Step 4 — Generate domain

Railway → main service → Settings → Networking → Generate Domain (port 8000).

### Step 5 — Update UI

Open `dsa-coach-ui.html`, change:
```javascript
const API = 'https://your-railway-url.up.railway.app/api/v1';
```

---

## Cost Management

Railway free tier gives $5/month credits. To stay within it:

- **Enable Serverless** on the main FastAPI service (sleeps when not in use)
- **Delete Celery Beat** from Railway (GitHub Actions handles cron for free)
- Keep only: FastAPI (serverless) + Celery Worker + PostgreSQL + Redis

Estimated cost: **$1–2/month** with these optimizations.

---

## Daily Workflow

```
1. Open dsa-coach-ui.html in browser (no terminals needed)
2. Dashboard shows today's motivation + current topic
3. Click "Get Today's Problem" or wait for 6 PM Telegram
4. Solve on LeetCode (struggle 30 min before hints)
5. Stuck? → Hint System → progressive 4-step unlock
6. Solved → Log Problem (30 sec)
7. Write Pattern Notes → AI validates → must pass before it counts
8. Ask Coach: explain concepts, review code, motivation
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/users` | Create user |
| GET | `/api/v1/users/{id}` | Get user |
| POST | `/api/v1/chat` | Talk to coach agent |
| GET | `/api/v1/progress/{user_id}` | Full progress profile |
| POST | `/api/v1/progress/{user_id}/advance-topic` | Move to next topic |
| POST | `/api/v1/problems/log` | Log solved problem |
| POST | `/api/v1/notes/submit` | Submit + validate notes |
| POST | `/api/v1/hints` | RAG-powered hint |
| POST | `/api/v1/nudge/trigger` | Manually trigger Telegram nudge |

---

## Common Issues & Fixes

| Error | Fix |
|-------|-----|
| `PermissionError` in Celery on Windows | Add `--pool=solo` flag |
| `psycopg2-binary` install fails | Use `pip install psycopg2-binary --only-binary=:all:` |
| `start.ps1` execution policy error | Run with `powershell -ExecutionPolicy Bypass -File .\start.ps1` |
| GitHub push blocked (secret scanning) | Never hardcode keys. Remove with `git reset HEAD~1` and repush |
| Railway crashes with `Field required` | Environment variables not set in Railway Variables tab |
| `Event loop is closed` in Celery | Fixed — uses `asyncio.new_event_loop()` per task |
| Groq model decommissioned | Update model name in `app/services/llm.py` to current model |
| ChromaDB warning at startup | Harmless — ChromaDB IS running, just API path mismatch |

---

## For AI Assistants Reading This README

If a new Claude/ChatGPT session is picking this up — full context:

**Built by:** Prasanna Teja (M_P_Teja) — beginner DSA learner who kept quitting after arrays.

**Current state (as of May 2026):**
- ✅ Fully deployed on Railway and working
- ✅ Telegram notifications firing via GitHub Actions at 6 PM IST
- ✅ User created on Railway Postgres: username `M_P_Teja`
- ✅ Frontend: `dsa-coach-ui.html` pointing to Railway URL
- ✅ Groq model: `llama3-70b-8192` (llama3-8b-8192 was decommissioned)
- ✅ Celery Beat deleted from Railway — GitHub Actions handles cron
- 🔄 ChromaDB running but RAG not fully tested end-to-end yet

**Railway services running:**
- Personalized-DSA-Coach (FastAPI, Serverless mode)
- celery (Celery Worker, always on)
- PostgreSQL
- Redis

**Key decisions made:**
- Python 3.11 forced via `.python-version` file (3.12+ breaks packages)
- Celery uses `--pool=solo` (prefork causes PermissionError on Windows/Linux)
- LLM auto-switches: `GROQ_API_KEY` set → Groq, not set → Ollama
- `APP_ENV=development` kept on Railway so DB tables auto-create on startup
- GitHub Actions replaces Celery Beat to save Railway credits
- Celery tasks use `asyncio.new_event_loop()` per task (fixes "event loop closed" on Linux)

**What to help with next:**
- User may need help with the chat/hint system if responses are slow or wrong
- Segment Tree and Trie (Phase 5) not tested yet
- System design phase after DSA completion not built yet

**Talk to the user directly and clearly. They understand the system well — no need to over-explain.**

---

## License

MIT — use it, modify it, make it your own coaching system.

---

*Built out of frustration with inconsistent DSA prep. If you're also stuck in the "start arrays, quit, restart" loop — this is for you.*
