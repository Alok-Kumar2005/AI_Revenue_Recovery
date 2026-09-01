# AI Revenue Recovery

> **Agent-powered platform** that detects at-risk revenue and executes compliant multi-channel recovery workflows across payment failures and checkout abandonment.

---

## Table of Contents

1. [Overview](#overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Quick Start — Local Development](#quick-start--local-development)
5. [Seed Data Generator](#seed-data-generator)
6. [Docker — Single-Command Deployment](#docker--single-command-deployment)
7. [Environment Variables Reference](#environment-variables-reference)
8. [API Reference](#api-reference)
9. [Verification Checklist](#verification-checklist)
10. [Troubleshooting](#troubleshooting)

---

## Overview

AI Revenue Recovery monitors payment pipelines in real time, classifies cases by risk tier (LOW → CRITICAL), and dispatches personalised recovery nudges via **Email**, **SMS**, and **WhatsApp** — all orchestrated by a LangGraph-powered AI agent.

### Key Capabilities

| Feature | Details |
|---|---|
| **Risk Classification** | ML model scores every failed payment (LOW / MEDIUM / HIGH / CRITICAL) |
| **AI Recovery Agent** | LangGraph agent selects optimal outreach strategy per case |
| **Multi-Channel Dispatch** | SendGrid (Email) · Twilio SMS · Twilio WhatsApp |
| **Audit Trail** | Immutable append-only log of every AI decision |
| **Dashboard** | Next.js 14 real-time KPI dashboard |
| **Webhooks** | Razorpay event ingestion endpoint |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI · Uvicorn · SQLAlchemy 2.0 · Alembic · Celery |
| **AI / ML** | LangGraph · LangChain · Google Gemini · scikit-learn |
| **Database** | PostgreSQL (Neon serverless) |
| **Frontend** | Next.js 14 · TypeScript · Tailwind CSS |
| **Messaging** | SendGrid · Twilio SMS · Twilio WhatsApp |
| **Payments** | Razorpay webhooks |
| **Containers** | Docker · Docker Compose |

---

## Project Structure

```
AI_Revenue_Recovery/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # SQLAlchemy ORM models
│   ├── database.py          # Engine + session setup
│   ├── config.py            # Pydantic settings
│   ├── seed_data.py         # ← Seed script (this step)
│   ├── Dockerfile           # Backend container
│   ├── agent/               # LangGraph recovery agent
│   ├── diagnosis/           # ML risk classifier
│   ├── execution/           # Message dispatchers
│   ├── routers/             # API route handlers
│   └── alembic/             # DB migrations
├── frontend/
│   ├── src/app/             # Next.js pages
│   ├── Dockerfile           # Frontend container (multi-stage)
│   └── package.json
├── docker-compose.yml       # ← Orchestration (this step)
├── .dockerignore
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quick Start — Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL instance (e.g. [Neon](https://neon.tech) free tier)
- Redis (optional — needed for Celery background tasks)

### 1 · Clone and configure

```bash
git clone https://github.com/your-org/AI_Revenue_Recovery.git
cd AI_Revenue_Recovery

# Copy the example env file and fill in your credentials
cp .env.example .env
```

### 2 · Backend setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the FastAPI server
uvicorn backend.main:app --reload --port 8000
```

### 3 · Frontend setup

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

---

## Seed Data Generator

The seed script populates the database with **18 realistic invoice recovery cases** across all risk tiers and payment statuses. It is safe to run repeatedly — it wipes all existing data before inserting fresh records.

### What gets seeded

| Entity | Count | Details |
|---|---|---|
| **Customers** | 10 | Diverse US & IN companies with realistic contact info |
| **Revenue Cases** | 18 | LOW (2) · MEDIUM (4) · HIGH (5) · CRITICAL (7) |
| **Interventions** | ~35 | EMAIL, SMS, WHATSAPP — varied delivery statuses |
| **Audit Logs** | ~140 | Complete lifecycle histories per case |
| **Recovery Metrics** | 7 | Daily KPI rollups for the last 7 days |

### Case distribution

| Risk Level | Statuses covered | Amount range |
|---|---|---|
| LOW | PENDING, RECOVERED | $250 – $476 |
| MEDIUM | PENDING, IN_RECOVERY, RECOVERED | $670 – $3,200 |
| HIGH | PENDING, IN_RECOVERY, RECOVERED, UNCOLLECTIBLE | $3,750 – $9,850 |
| CRITICAL | PENDING, IN_RECOVERY, RECOVERED, UNCOLLECTIBLE | $6,300 – $15,000 |

### Run the seed script

```bash
# From the project root:

# Interactive mode (asks for confirmation)
python backend/seed_data.py

# Non-interactive (CI / Docker entrypoint)
python backend/seed_data.py --confirm
```

**Expected output:**

```
WARNING: This will WIPE ALL existing data and re-seed the database.
  Type 'yes' to continue: yes

  Seeding AI Revenue Recovery database...

  Wiping existing data...
  Existing data cleared.

  Creating customers...
  10 customers created.

  Creating revenue cases, interventions, and audit logs...
  18 revenue cases created.
  35 interventions created.
  141 audit log entries created.

  Seeding recovery metrics (last 7 days)...
  Recovery metrics seeded.

==================================================
  Seed complete!
      Customers    : 10
      Cases        : 18
      Interventions: 35
      Audit logs   : 141
==================================================
```

> **Note:** The seed script connects using the `POSTGRESS_URL` from your `.env` file. Make sure the database is reachable and `alembic upgrade head` has been run first.

---

## Docker — Single-Command Deployment

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose v2)
- A populated `.env` file (copy from `.env.example`)

### 1 · Prepare environment

```bash
cp .env.example .env
# Edit .env with your PostgreSQL URL, Razorpay keys, etc.
```

### 2 · Build and start all services

```bash
docker-compose up --build
```

This single command will:

1. **Build** the backend image (`python:3.11-slim`, installs `requirements.txt`)
2. **Build** the frontend image (3-stage `node:18-alpine`, produces optimised Next.js bundle)
3. **Start** both containers on a shared `recovery_net` bridge network
4. **Health-check** the backend every 30 s — the frontend only starts once the backend is healthy

### 3 · Access the services

| Service | URL |
|---|---|
| Frontend Dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Interactive Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

### 4 · Run in the background

```bash
docker-compose up -d --build
docker-compose logs -f             # tail all logs
docker-compose logs -f backend     # tail backend only
```

### 5 · Stop and clean up

```bash
docker-compose down           # stop containers (keeps volumes)
docker-compose down -v        # stop + remove named volumes
```

### Seeding inside Docker

After the backend container is running:

```bash
docker-compose exec backend python backend/seed_data.py --confirm
```

---

## Environment Variables Reference

Copy `.env.example` to `.env` and fill in the values below.

| Variable | Required | Description |
|---|---|---|
| `POSTGRESS_URL` | ✅ | Full PostgreSQL connection string (Neon, Supabase, or local) |
| `RZP_KEY` | ✅ | Razorpay API key |
| `RZP_SECRET` | ✅ | Razorpay API secret |
| `RZP_WEBHOOK_SECRET` | ✅ | Razorpay webhook signing secret |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key for the LLM agent |
| `REDIS_URL` | ⬜ | Redis URL for Celery (omit to run in eager/sync mode) |
| `SENDGRID_API_KEY` | ⬜ | SendGrid key for Email dispatch |
| `FROM_EMAIL` | ⬜ | Sender address for recovery emails |
| `TWILIO_ACCOUNT_SID` | ⬜ | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | ⬜ | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | ⬜ | Twilio E.164 SMS number |
| `TWILIO_WHATSAPP_NUMBER` | ⬜ | Twilio WhatsApp sender (e.g. `whatsapp:+14155238886`) |
| `MOCK_DISPATCH` | ⬜ | `True` to log mock messages instead of real API calls (default: `True`) |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service status |
| `GET` | `/health` | DB connectivity check |
| `POST` | `/webhook/razorpay` | Ingest Razorpay payment events |
| `GET` | `/api/metrics/summary` | Live KPI aggregates for the dashboard |
| `GET` | `/api/cases` | Paginated list of revenue cases |
| `GET` | `/api/cases/{case_id}` | Case detail + full audit trail |
| `GET` | `/api/interventions` | Recent intervention records |

Full interactive docs: **http://localhost:8000/docs**

---

## Verification Checklist

Run through the following after `docker-compose up --build` to confirm everything is working:

### Infrastructure

- [ ] `docker-compose ps` shows both `ai_recovery_backend` and `ai_recovery_frontend` as **healthy**
- [ ] No port binding errors on 3000 or 8000
- [ ] Backend logs show `"Neon PostgreSQL connection: OK"` on startup

### Backend API

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected"}

# Cases list (empty until seeded)
curl http://localhost:8000/api/cases
```

### Seed and Verify Data

```bash
# Seed the database
python backend/seed_data.py --confirm
# or inside Docker:
docker-compose exec backend python backend/seed_data.py --confirm

# Verify cases were created
curl "http://localhost:8000/api/cases?limit=5" | python -m json.tool

# Verify metrics
curl http://localhost:8000/api/metrics/summary | python -m json.tool
```

### Frontend Dashboard

- [ ] Open http://localhost:3000 — dashboard loads with KPI cards
- [ ] Cases table displays seeded records across all risk tiers
- [ ] Risk tier colour coding is visible (LOW green · MEDIUM yellow · HIGH orange · CRITICAL red)

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`

Run the seed script from the **project root**, not from inside `backend/`:

```bash
# Correct
python backend/seed_data.py

# Incorrect
cd backend && python seed_data.py
```

### Database connection refused

1. Verify `POSTGRESS_URL` in `.env` is correct and the Neon instance is active.
2. Check firewall / VPN settings — Neon requires outbound TCP on port 5432.
3. Run `alembic upgrade head` before the seed script.

### `docker-compose up` port already in use

```bash
# Find what's using port 8000 or 3000
netstat -ano | findstr :8000     # Windows
lsof -i :8000                    # macOS / Linux

# Or change the host port in docker-compose.yml:
ports:
  - "8001:8000"    # expose as 8001 on the host
```

### Frontend shows "Failed to fetch" / network errors

Inside Docker, the frontend container reaches the backend via the service name `backend` on the internal `recovery_net` network. If you're running the frontend locally (not in Docker), update `frontend/next.config.js` to point to `http://localhost:8000`.

### CORS errors in browser console

The `CORSMiddleware` in `backend/main.py` allows `http://localhost:3000`. If your frontend runs on a different origin, add it to the `allow_origins` list.