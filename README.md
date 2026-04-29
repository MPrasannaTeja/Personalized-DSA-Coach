# DSA Coach — Fullstack

Fullstack agentic platform for personalized DSA learning.  
**Backend Stack**: FastAPI · LangGraph · Claude (Anthropic) · PostgreSQL · ChromaDB · Celery · Redis · Telegram  
**Frontend**: HTML5 · JavaScript · Fetch API

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (dsa-coach-ui.html)                                       │
│  ├─ User profile & progress dashboard                              │
│  ├─ Chat interface with DSA Coach agent                            │
│  └─ Problem submissions & notes input                              │
│                                                                     │
│  POST /api/v1/chat  ──► FastAPI ──► LangGraph Coach Graph          │
│                                          │                          │
│                              ┌───────────┤                          │
│                              │           │                          │
│                         RAG Prefetch   Coach Node (Claude)         │
│                         (ChromaDB)         │                        │
│                              │         Tool Node                   │
│                              │    (validate_notes /                │
│                              │     log_problem /                   │
│                              │     query_past_struggles)           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Celery Beat (cron 6 PM)                                           │
│  send_daily_nudge_to_all_users                                      │
│    └─► per-user: get_user_profile → LLM assignment → Telegram      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
dsa-coach/
├── Frontend
│   └── dsa-coach-ui.html            # Single-page HTML5 app (JavaScript)
│       ├── User profile & progress
│       ├── Chat with DSA Coach
│       ├── Problem tracking
│       └── Fetches from backend API
├── Backend (FastAPI)
│   ├── app/
│   │   ├── main.py                      # FastAPI app factory + lifespan
│   │   ├── config.py                    # Pydantic settings (reads .env)
│   │   ├── api/
│   │   │   ├── schemas.py               # Pydantic request/response models
│   │   │   └── routes/
│   │   │       ├── chat.py              # POST /chat — main agent endpoint
│   │   │       └── routes.py            # users / progress / problems / notes / hints / nudge
│   │   ├── agent/
│   │   │   ├── coach_graph.py           # LangGraph graph definition
│   │   │   ├── prompts/
│   │   │   │   └── coach_prompts.py     # All LLM prompts + phase/topic data
│   │   │   └── tools/
│   │   │       └── coach_tools.py       # LangChain tools (validate_notes, log_problem, etc.)
│   │   ├── db/
│   │   │   ├── models.py                # SQLAlchemy ORM models
│   │   │   ├── session.py               # Async engine + session factory
│   │   │   └── migrations/
│   │   │       └── env.py               # Alembic config
│   │   ├── services/
│   │   │   ├── llm.py                   # LLM singleton factory
│   │   │   ├── vector_store.py          # ChromaDB client (upsert + query)
│   │   │   ├── progress_service.py      # All DB operations for progress tracking
│   │   │   └── telegram_service.py      # Telegram Bot API wrapper
│   │   └── workers/
│   │       ├── celery_app.py            # Celery app + beat schedule
│   │       └── tasks.py                 # Celery tasks (daily nudge, chroma sync)
│   ├── tests/
│   │   ├── unit/test_core.py            # Unit tests (no infra needed)
│   │   └── integration/test_api.py      # Integration tests (needs Postgres)
│   ├── docker-compose.yml               # Postgres + Redis + ChromaDB
│   ├── pyproject.toml                   # Dependencies + tool config
│   └── .env.example                     # Environment variable template
└── README.md                            # This file
```

---

## Quick Start

### 1. Set up environment

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, APP_SECRET_KEY
```

### 2. Start infrastructure (Postgres, Redis, ChromaDB)

```bash
docker-compose up -d
# Wait ~10 seconds for services to be healthy
docker-compose ps   # all should show "healthy"
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 4. Run database migrations

```bash
# Development: tables auto-created on startup (see lifespan in main.py)
# Production: use Alembic
alembic init app/db/migrations      # first time only
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 5. Start the FastAPI backend

```bash
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 6. Start Celery worker + scheduler

```bash
# Terminal 1 — worker
celery -A app.workers.celery_app worker --loglevel=info

# Terminal 2 — beat scheduler (sends 6 PM cron)
celery -A app.workers.celery_app beat --loglevel=info

# Dev shortcut (worker + beat combined):
celery -A app.workers.celery_app worker --beat --loglevel=info
```

### 7. Open the frontend

```bash
# Open dsa-coach-ui.html in your browser
# File → Open... → dsa-coach-ui.html
# Or serve via local HTTP server:

python -m http.server 3000
# Then visit http://localhost:3000/dsa-coach-ui.html
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/users` | Create user |
| GET | `/api/v1/users/{id}` | Get user |
| POST | `/api/v1/chat` | Send message to coach agent |
| GET | `/api/v1/progress/{user_id}` | Get full progress profile |
| POST | `/api/v1/progress/{user_id}/advance-topic` | Advance to next topic |
| POST | `/api/v1/problems/log` | Log a solved problem |
| POST | `/api/v1/notes/submit` | Submit + validate pattern notes |
| POST | `/api/v1/hints` | Get RAG-powered hint |
| POST | `/api/v1/nudge/trigger` | Manually trigger daily nudge |

### Example: Create user + chat

```bash
# 1. Create a user
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username": "yourname", "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID"}'

# 2. Chat with the coach (use the user_id from step 1)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "USER_UUID_HERE", "message": "Give me today'\''s problem"}'

# 3. Submit pattern notes after solving
curl -X POST http://localhost:8000/api/v1/notes/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_UUID_HERE",
    "topic_id": "arrays",
    "pattern_name": "Sliding Window",
    "note_text": "Pattern: Sliding Window. Applies here because we need max sum subarray of size k. Maintain a running sum, subtract left element and add right element each step. Key insight: O(n) vs O(n*k) brute force. Recognize next time when: fixed window size + array/string."
  }'

# 4. Log a solved problem
curl -X POST http://localhost:8000/api/v1/problems/log \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_UUID_HERE",
    "topic_id": "arrays",
    "problem_name": "643. Maximum Average Subarray I",
    "difficulty": "easy",
    "used_hint": false
  }'
```

### Get your Telegram Chat ID

1. Message `@userinfobot` on Telegram
2. It replies with your chat ID
3. Set it when creating your user account

---

## Frontend (HTML5 UI)

The **dsa-coach-ui.html** file is a standalone HTML5 + JavaScript single-page app. No build step required.

### Features
- **User Authentication**: Create/login to your account
- **Dashboard**: View progress, streaks, and topic mastery
- **Chat Interface**: Talk to the DSA Coach agent in real-time
- **Problem Tracking**: Log solved problems and track difficulty progression
- **Notes Input**: Submit pattern notes and get LLM validation feedback
- **Daily Assignments**: View personalized assignments sent by the system

### Running the Frontend

**Option 1: Direct browser open**
```bash
# Open dsa-coach-ui.html directly in your browser
# File → Open... → select dsa-coach-ui.html
```

**Option 2: Local HTTP server (recommended for testing)**
```bash
python -m http.server 3000
# Then visit http://localhost:3000/dsa-coach-ui.html
```

**Option 3: Deploy to production**
- Copy `dsa-coach-ui.html` to any static hosting (AWS S3, Netlify, Vercel, etc.)
- The HTML file connects to your backend API via fetch() calls
- Ensure CORS is enabled on your FastAPI backend (see [main.py](main.py))

### Frontend <→ Backend Communication

The frontend makes fetch requests to the following API endpoints:

```javascript
// Create or login user
POST http://localhost:8000/api/v1/users

// Chat with coach
POST http://localhost:8000/api/v1/chat
body: { user_id, message }

// Get progress profile
GET http://localhost:8000/api/v1/progress/{user_id}

// Submit notes
POST http://localhost:8000/api/v1/notes/submit
body: { user_id, topic_id, pattern_name, note_text }

// Log solved problem
POST http://localhost:8000/api/v1/problems/log
body: { user_id, topic_id, problem_name, difficulty, used_hint }
```

All requests are sent with `Content-Type: application/json` headers. Responses are JSON.

---

## How the Agent Works

### Chat flow (LangGraph)
```
User message
  → rag_prefetch_node: queries ChromaDB for similar past notes
  → coach_node: Claude with system prompt (context + RAG results)
      → if tool_call: tools_node executes tool, result fed back to coach_node
      → if no tool_call: return response to user
```

### Daily nudge flow (Celery)
```
6 PM cron
  → query all users with notifications_enabled + telegram_chat_id
  → per user: get_user_profile → compute dynamic difficulty
  → LLM generates personalised motivational message + specific problem assignments
  → save to daily_assignments table
  → send via Telegram Bot API
```

### Notes validation (Strict Coach guardrail)
```
Student submits notes
  → LLM validates: does it name the pattern? explain WHY? describe key insight?
  → score 1-10; approved only if score >= 6
  → if approved: persist to Postgres + ChromaDB (for future RAG)
  → if rejected: return specific feedback, do NOT mark problem as clean
```

---

## Running Tests

```bash
# Unit tests (no infra needed)
pytest tests/unit/ -v

# Integration tests (requires running Postgres)
TEST_DATABASE_URL="postgresql://dsa_coach:changeme@localhost:5432/dsa_coach_test" \
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=app --cov-report=term-missing
```

---

## Production Deployment Checklist

- [ ] Set `APP_ENV=production` in environment
- [ ] Use a proper secret for `APP_SECRET_KEY` (32+ chars)
- [ ] Run `alembic upgrade head` before starting app
- [ ] Use `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app` instead of uvicorn directly
- [ ] Set up separate Celery worker and beat processes (not combined)
- [ ] Add authentication (API key / JWT) to all endpoints
- [ ] Set up monitoring (Sentry + Prometheus)
- [ ] Configure Postgres connection pooling (PgBouncer)
- [ ] Back up ChromaDB volume regularly
