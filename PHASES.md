# VJob — Build Phases

## Phase 1: Project Scaffold & Data Foundation (CURRENT)
**Status**: Complete
**What's done**:
- FastAPI backend with async SQLAlchemy + PostgreSQL
- React + Vite + TypeScript + Tailwind frontend
- Database models: Company, Job, UserProfile, Application
- Pydantic v2 schemas for all models
- REST API endpoints for companies, jobs, profiles, applications
- Top 100 SE company seed data with ATS platform classification
- Seed script to populate companies table
- Docker Compose for backend + frontend + PostgreSQL
- Alembic for database migrations
- `.env` configuration system

## Phase 2: Scraping Engine (NEXT)
**Planned**:
- ATS-specific parsers (Greenhouse, Lever, Ashby, Workday, custom)
- Per-company career page scraper using httpx + Playwright fallback
- LLM-based job extraction from raw HTML (structured output)
- Content-hash delta detection (only re-parse changed pages)
- APScheduler for 2–4 hour real-time fetch cycles
- Job deduplication across sources
- Scraping status tracking per company (last_scraped, success/fail, error logs)

## Phase 3: Profile & Scoring
**Planned**:
- Resume PDF upload + LLM extraction into structured UserProfile
- LinkedIn profile import (manual paste, not scraping)
- Job scoring engine: skills match, seniority fit, location, compensation alignment
- Skill gap analysis: "you have 7/12 required skills, missing X, Y, Z"
- Transparent scoring weights visible to user
- Red flag / ghost posting detection on job descriptions

## Phase 4: Application Optimization
**Planned**:
- Resume-Job matcher with keyword gap analysis
- Resume tailoring: LLM rewrites bullets, reorders sections per target job
- Cover letter generator referencing company signals
- Outreach draft writer (LinkedIn message, cold email, referral request)
- Version tracking for resume variants per application

## Phase 5: Pipeline & Tracking
**Planned**:
- Kanban-style application pipeline (saved → applied → interviewing → offer)
- Follow-up scheduler with optimal timing and drafted messages
- Interview prep generator (role-specific questions, company talking points)
- Daily briefing endpoint (new jobs, follow-ups due, hiring signals)

## Phase 6: Continuous Intelligence
**Planned**:
- Hiring signal detection (funding rounds, headcount growth, product launches)
- Market pulse tracker (skill demand trends, salary ranges)
- Rejection pattern analyzer (cross-application learning)
- Skill micro-credential mapper (fastest path to close gaps)
- Company health check (layoffs, Glassdoor sentiment)