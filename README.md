# 🧠 Personalized DSA Coach Agent

> A fully agentic, AI-powered DSA coaching system that assigns daily problems, gives progressive hints, validates your pattern notes, tracks your progress, and sends Telegram reminders — all personalized to how fast or slow you're actually learning.

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
- Sends me a Telegram message at 6 PM every day whether my laptop is open or not

---

## What This Project Does

```
You solve on LeetCode
    ↓
Log it in the UI (2 min)
    ↓
Write pattern notes → AI validates them → stored in vector DB
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
| LLM (local) | Ollama + llama2 | Free, runs on your laptop |
| LLM (cloud) | Groq (llama3-8b) | Free API, fast, works on Railway |
| Database | PostgreSQL + SQLAlchemy | Stores all progress, streaks, notes |
| Vector Store | ChromaDB | Semantic search over your past notes (RAG) |
| Background Jobs | Celery + Redis | Daily 6 PM cron job |
| Notifications | Telegram Bot API | Daily problem assignment to phone |
| Deployment | Railway | Free tier, auto-deploys from GitHub |
| Frontend | Vanilla HTML/CSS/JS | Single file, open directly in browser |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (dsa-coach-ui.html)                            │
│  Opens locally — talks to Railway backend via HTTP      │
└────────────────────┬────────────────────────────────────┘
                     │ API calls
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Railway (Cloud — always running)                       │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  FastAPI    │  │ Celery Worker│  │  Celery Beat  │  │
│  │  :8000      │  │ (tasks)      │  │  (6 PM cron)  │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                │                  │           │
│  ┌──────▼──────┐  ┌──────▼───────────────────▼───────┐  │
│  │  LangGraph  │  │           Redis                   │  │
│  │  Coach Agent│  │    (Celery broker + results)      │  │
│  │  + Groq LLM │  └──────────────────────────────────┘  │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐  ┌──────────────┐                      │
│  │ PostgreSQL  │  │   ChromaDB   │                      │
│  │ (progress,  │  │ (pattern     │                      │
│  │  streaks,   │  │  notes RAG)  │                      │
│  │  notes)     │  │              │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼ Telegram Bot API
              📱 Your Phone (6 PM daily)
```

---

## The 5 Learning Phases

The system tracks you through a structured 4–6 month roadmap:

| Phase | Topics | Min Problems | Duration |
|-------|--------|-------------|----------|
| 1 — Foundation | Arrays, Binary Search, Linked Lists | 37 | Weeks 1–3 |
| 2 — Big Unlock | Recursion, Trees & BST, Heaps | 49 | Weeks 4–8 |
| 3 — Graph World | Graphs, Advanced Graphs (Dijkstra etc.) | 30 | Weeks 9–13 |
| 4 — DP Demystified | DP Foundation, Knapsack, LCS/LIS | 38 | Weeks 14–20 |
| 5 — Interview Mode | Trie, Segment Tree, Random Mixed | 46 | Weeks 21–24 |

**Total: ~200 minimum problems.** In practice 300–400+ because you revisit weak areas.

### Dynamic difficulty adjustment
- Clean solve rate > 70% + hint rate < 30% → pushes to **Hard**, assigns 3 problems/day
- Clean solve rate > 50% → **Medium**, 2 problems/day
- Below that → **Easy**, 1 problem/day, slow down

---

## The 32 Patterns Tracked

Across all phases the system tracks these patterns from the DSA Patterns cheat sheet:

**Arrays & Strings:** Two Pointers, Sliding Window, Prefix Sum, Kadane's Algorithm, Monotonic Stack, Binary Search (8 variants)

**Linked Lists:** Fast & Slow Pointers, Reverse In-Place, Dummy Head Node, Floyd's Cycle, Merge Two Lists

**Trees & Graphs:** BFS Level Order, DFS Preorder/Inorder/Postorder, Topological Sort, Union-Find, Dijkstra's, Backtracking, Island/Flood Fill, LCA, Tree Diameter

**Dynamic Programming:** 1D DP Array, 2D Grid DP, 0/1 Knapsack, Unbounded Knapsack, LCS Pattern, LIS Pattern

**Advanced:** Trie, Heap/Priority Queue, Segment Tree, Bit Manipulation

---

## Key Features

### 1. Progressive Hint System (No Cheating)
```
Stuck on a problem?
  Step 1: Struggle for 30 min (timer starts)
  Step 2: Name the pattern → unlocks hint
  Step 3: Get a clue (pattern + one concrete hint, no code)
  Step 4: Full solution unlocked → BUT you must write notes first
           before the problem gets logged as solved
```

### 2. Notes Validation (The Strict Coach Guardrail)
The most important feature. You write notes, the AI validates them. Vague notes get rejected.

**Rejected (score 2/10):**
> "Used sliding window"

**Approved (score 8/10):**
> "Pattern: Sliding Window. Applies here because we need max sum of exactly k consecutive elements. Instead of recalculating from scratch each time O(n*k), maintain a running sum by subtracting left and adding right as we slide — O(n). Recognize next time when: fixed subarray size + need max/min/sum."

Approved notes get stored in ChromaDB as embeddings.

### 3. RAG-Powered Personalized Hints
When you ask for a hint, the system doesn't give a generic response. It:
1. Searches ChromaDB for problems YOU struggled with that are semantically similar
2. Identifies your recurring blind spots (patterns you struggled with 2+ times)
3. Tailors the hint to your specific history

### 4. Daily Telegram Notification (Cloud, Automatic)
Every day at 6 PM IST, Celery Beat triggers a job that:
- Reads your current phase, topic, streak from PostgreSQL
- Computes your dynamic difficulty (based on clean-solve rate)
- Calls Groq LLM to generate a personalised motivational message + specific LeetCode problems
- Sends it to your Telegram

Works even when your laptop is off.

### 5. Streak Tracking
- Solve at least 1 problem and log it → streak continues
- Miss a day → streak resets to 0
- Streak is shown in the UI and referenced in daily Telegram messages

---

## Project Structure

```
dsa-coach-backend/
├── app/
│   ├── main.py                          # FastAPI app factory + lifespan startup
│   ├── config.py                        # All settings via pydantic-settings (.env)
│   │
│   ├── api/
│   │   ├── schemas.py                   # Pydantic request/response models
│   │   └── routes/
│   │       ├── chat.py                  # POST /chat → LangGraph agent
│   │       └── routes.py               # /users /progress /problems /notes /hints /nudge
│   │
│   ├── agent/
│   │   ├── coach_graph.py               # LangGraph graph: rag_prefetch → coach → tools
│   │   ├── prompts/
│   │   │   └── coach_prompts.py         # All LLM prompts + 5-phase roadmap data
│   │   └── tools/
│   │       └── coach_tools.py           # LangChain tools the agent can call
│   │
│   ├── db/
│   │   ├── models.py                    # SQLAlchemy ORM: users, topic_progress,
│   │   │                               #   solved_problems, pattern_notes, daily_assignments
│   │   ├── session.py                   # Async engine + session factory
│   │   └── migrations/env.py            # Alembic config
│   │
│   ├── services/
│   │   ├── llm.py                       # LLM factory: Groq (cloud) / Ollama (local)
│   │   ├── vector_store.py              # ChromaDB: upsert + semantic query
│   │   ├── progress_service.py          # All DB operations for progress tracking
│   │   └── telegram_service.py          # Telegram Bot API wrapper
│   │
│   └── workers/
│       ├── celery_app.py                # Celery app + beat schedule (6 PM cron)
│       └── tasks.py                     # send_daily_nudge, send_nudge_to_user,
│                                        #   sync_notes_to_chroma
│
├── tests/
│   ├── unit/test_core.py                # Unit tests (no infra needed)
│   └── integration/test_api.py          # Integration tests
│
├── dsa-coach-ui.html                    # Frontend (single file, open in browser)
├── docker-compose.yml                   # Postgres + Redis + ChromaDB for local dev
├── Procfile                             # Railway: web, worker, beat processes
├── railway.json                         # Railway deployment config
├── pyproject.toml                       # Dependencies
├── requirements.txt                     # Flat requirements for Railway build
├── start.ps1                            # Windows: one-click start all services
└── .env.example                         # Template for environment variables
```

---

## Database Schema

```
users
  id, username, telegram_chat_id
  current_phase_idx, current_topic_idx
  streak, last_solved_date, total_problems_solved
  start_date, notifications_enabled

topic_progress  (one row per user per topic)
  user_id → users.id
  topic_id, topic_name, phase_idx
  solved_easy, solved_medium, solved_hard
  hint_used_count, clean_solve_count, total_solved
  is_completed, completed_at

solved_problems  (one row per solved problem)
  user_id → users.id
  topic_id, leetcode_number, problem_name
  difficulty, patterns_used
  used_hint, clean_solve, notes_submitted
  time_taken_minutes, solved_at

pattern_notes  (one row per approved note)
  user_id → users.id
  topic_id, pattern_name, note_text
  chroma_doc_id, synced_to_chroma
  created_at

daily_assignments  (one row per day per user)
  user_id → users.id
  assignment_date, phase_idx, topic_id
  motivational_message, problem_assignment
  recommended_difficulty, recommended_count
  telegram_sent, telegram_sent_at
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/users` | Create user account |
| GET | `/api/v1/users/{id}` | Get user |
| POST | `/api/v1/chat` | Send message to coach agent |
| GET | `/api/v1/progress/{user_id}` | Full progress profile |
| POST | `/api/v1/progress/{user_id}/advance-topic` | Move to next topic |
| POST | `/api/v1/problems/log` | Log a solved problem |
| POST | `/api/v1/notes/submit` | Submit + validate pattern notes |
| POST | `/api/v1/hints` | Get RAG-powered hint |
| POST | `/api/v1/nudge/trigger` | Manually trigger daily Telegram nudge |

---

## Local Development Setup

### Prerequisites
- Python 3.11 (specifically — not 3.12/3.13/3.14)
- Docker Desktop (running)
- Ollama installed with llama2 pulled (`ollama pull llama2`)
- Git

### Step 1 — Clone and setup

```bash
git clone https://github.com/MPrasannaTeja/Personalized-DSA-Coach.git
cd Personalized-DSA-Coach

# Create venv with Python 3.11 specifically
py -3.11 -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2 — Configure environment

```bash
cp .env.example .env
```

Fill in your `.env`:
```env
# Required for local dev:
GROQ_API_KEY=               # leave empty to use Ollama locally
OLLAMA_MODEL=llama2
TELEGRAM_BOT_TOKEN=         # from @BotFather on Telegram
TELEGRAM_DEFAULT_CHAT_ID=   # from @userinfobot on Telegram
APP_SECRET_KEY=             # run: python -c "import secrets; print(secrets.token_hex(32))"

# These defaults work with docker-compose as-is:
DATABASE_URL=postgresql+asyncpg://dsa_coach:changeme@localhost:5432/dsa_coach
DATABASE_URL_SYNC=postgresql://dsa_coach:changeme@localhost:5432/dsa_coach
REDIS_URL=redis://localhost:6379/0
```

### Step 3 — Start infrastructure

```bash
docker-compose up -d
# Wait 20 seconds, then verify:
docker-compose ps   # all 3 should show "healthy"
```

### Step 4 — Start everything (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

This opens 3 terminals automatically:
- FastAPI backend on `localhost:8000`
- Celery Worker (background tasks)
- Celery Beat (6 PM scheduler)

### Step 5 — Create your user

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/users" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username": "yourname", "telegram_chat_id": "YOUR_TELEGRAM_ID"}' `
  -UseBasicParsing
```

Save the `id` from the response — this is your USER_ID used everywhere.

### Step 6 — Open the UI

Open `dsa-coach-ui.html` in your browser. Paste your USER_ID in the sidebar. Done.

---

## Cloud Deployment (Railway)

Deploy to Railway so Telegram notifications work 24/7 without your laptop.

### Step 1 — Set up Railway

1. Go to [railway.app](https://railway.app) → sign in with GitHub
2. New Project → Deploy from GitHub repo → select this repo
3. Add addons: PostgreSQL + Redis (both free)

### Step 2 — Set environment variables

In Railway → your service → Variables tab:

```
GROQ_API_KEY              = gsk_your_key_from_console.groq.com
TELEGRAM_BOT_TOKEN        = your_bot_token
TELEGRAM_DEFAULT_CHAT_ID  = your_chat_id
APP_SECRET_KEY            = your_secret_key
APP_ENV                   = production
DATABASE_URL              = (Railway auto-fills from Postgres addon)
REDIS_URL                 = (Railway auto-fills from Redis addon)
CELERY_BROKER_URL         = (same as REDIS_URL)
CELERY_RESULT_BACKEND     = (same as REDIS_URL, change /0 to /1)
DAILY_NUDGE_TIMEZONE      = Asia/Kolkata
DAILY_NUDGE_HOUR          = 18
DAILY_NUDGE_MINUTE        = 0
```

### Step 3 — Add Worker and Beat services

Railway needs 3 separate services. After the first (web) deploys:

**Worker service:**
- New Service → GitHub Repo → same repo
- Settings → Start Command: `celery -A app.workers.celery_app worker --loglevel=info --pool=solo`

**Beat service:**
- New Service → GitHub Repo → same repo
- Settings → Start Command: `celery -A app.workers.celery_app beat --loglevel=info`

### Step 4 — Update the UI to point to Railway

Open `dsa-coach-ui.html`, find line:
```javascript
const API = 'http://localhost:8000/api/v1';
```
Change to:
```javascript
const API = 'https://your-service-name.railway.app/api/v1';
```

---

## How to Use It Daily

### The workflow

```
1. Open dsa-coach-ui.html in browser
2. Dashboard shows today's topic + progress
3. Click "Get Today's Problem" → coach assigns specific LeetCode problems
4. Solve on LeetCode (struggle at least 30 min before hints)
5. Stuck? → Hint System → progressive 4-step unlock
6. Solved → Log Problem (30 seconds)
7. Write Pattern Notes → AI validates → must pass before it counts
8. Ask Coach anything — explain concepts, review your code, motivation
```

### When Telegram arrives (6 PM)

The message includes:
- Your current streak
- A personalised motivational message based on your actual progress
- 2–3 specific LeetCode problems with exact names and numbers
- What pattern to focus on for each problem

### How to ask Coach to explain optimal solutions

After getting a suboptimal LeetCode result:
```
"LeetCode 643. My solution beats only 40% — here's my code: [paste]
It's O(n*k). Show me the optimal approach and explain WHY mine is slow."
```

Then write notes about what you learned → they get stored and referenced in future hints.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Cloud only | Free at console.groq.com — used on Railway |
| `OLLAMA_MODEL` | Local only | Model name, default `llama2` |
| `OLLAMA_BASE_URL` | Local only | Default `http://localhost:11434` |
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather on Telegram |
| `TELEGRAM_DEFAULT_CHAT_ID` | Yes | From @userinfobot on Telegram |
| `DATABASE_URL` | Yes | PostgreSQL async URL (asyncpg) |
| `DATABASE_URL_SYNC` | Yes | PostgreSQL sync URL (psycopg2) |
| `REDIS_URL` | Yes | Redis connection URL |
| `CELERY_BROKER_URL` | Yes | Same as REDIS_URL |
| `CELERY_RESULT_BACKEND` | Yes | Redis URL with /1 database |
| `APP_SECRET_KEY` | Yes | 32+ char random string |
| `APP_ENV` | No | `development` or `production` |
| `DAILY_NUDGE_HOUR` | No | Hour for daily notification (default 18) |
| `DAILY_NUDGE_TIMEZONE` | No | Timezone (default Asia/Kolkata) |

---

## Running Tests

```bash
# Unit tests (no infra needed)
pytest tests/unit/ -v

# Integration tests (requires running Postgres)
pytest tests/integration/ -v

# All with coverage
pytest --cov=app --cov-report=term-missing
```

---

## Health Verification

```powershell
# FastAPI
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# Ollama
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing

# Redis
docker exec dsa_redis redis-cli ping   # should return PONG

# PostgreSQL
docker exec dsa_postgres psql -U dsa_coach -d dsa_coach -c "SELECT username, streak FROM users;"

# ChromaDB
Invoke-WebRequest -Uri "http://localhost:8001/api/v1/heartbeat" -UseBasicParsing
```

---

## Common Issues

**Celery worker crashes on Windows (PermissionError)**
```powershell
# Add --pool=solo flag — this is the fix for Windows
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

**psycopg2-binary fails to install**
```powershell
# Use --only-binary flag to force pre-built wheel
pip install psycopg2-binary --only-binary=:all:
```

**ChromaDB warning at startup**
```
⚠️ ChromaDB not reachable at startup
```
This is a harmless API path mismatch. ChromaDB IS running — notes save correctly. Ignore it.

**start.ps1 execution policy error**
```powershell
# Use this instead of .\start.ps1
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

**GitHub push rejected (secret scanning)**
Never hardcode API keys in Python files. Keys only go in `.env` (local) or Railway Variables (cloud). If a key got committed, remove it and use `git reset HEAD~1` before pushing again.

---

## For AI Assistants Reading This

If a new Claude/ChatGPT session is picking this up from the GitHub URL — here's the full context:

**This project was built by a beginner DSA learner (Prasanna Teja)** who kept quitting DSA preparation. The system is designed around his specific failure patterns: quitting after arrays, never reaching DP/Trees/Heaps, and learning nothing from seeing solutions.

**Current state of the project:**
- Backend fully built and running locally ✅
- User created: username `M_P_Teja` ✅
- Local stack: Ollama (llama2) + PostgreSQL + Redis + ChromaDB via Docker ✅
- Frontend: `dsa-coach-ui.html` (vanilla HTML, talks to FastAPI) ✅
- Railway deployment: in progress (Groq added for cloud LLM) 🔄
- Telegram notifications: configured, needs full Railway deploy to work 24/7 🔄

**Key decisions made:**
- Python 3.11 specifically (3.12+ breaks some packages)
- Celery uses `--pool=solo` on Windows (prefork causes PermissionError)
- LLM auto-switches: `GROQ_API_KEY` set → Groq, not set → Ollama
- `.env` never committed — keys only in `.env` locally, Railway Variables on cloud

**What the user needs help with next:**
- Completing Railway deployment (PostgreSQL + Redis addons, Worker + Beat services)
- Updating `dsa-coach-ui.html` API URL from localhost to Railway URL
- Verifying 6 PM Telegram notification works end-to-end from cloud

**Personality note:** The user is sharp, asks good architectural questions, and understands the system well. Explain things clearly without being condescending. When something breaks, diagnose from the error message directly — don't ask too many clarifying questions.

---

## License

MIT — use it, modify it, make it your own coaching system.

---

*Built out of frustration with inconsistent DSA prep. If you're also stuck in the "start arrays, quit, restart" loop — this is for you.*
