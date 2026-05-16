# VJob — AI-Powered Job Intelligence Agent

## Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- **Frontend**: React + Vite + TypeScript + TailwindCSS
- **AI**: OpenAI/Anthropic for job extraction, scoring, resume tailoring
- **Scraping**: httpx + Playwright + LLM parsing

## Quick Start

```bash
# Copy env file
cp .env.example .env

# Start everything
docker compose up --build

# Seed the top 100 companies
docker compose exec backend python -m app.seed

# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

## Build Phases
See [PHASES.md](./PHASES.md) for full phase breakdown and current status.