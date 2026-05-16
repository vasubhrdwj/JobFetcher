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

## Phase 2: Scraping Engine (CURRENT)
**Status**: Complete
**What's done**:
- ATS-specific parsers: Greenhouse (API), Lever (API + HTML fallback), Workday, iCIMS, Ashby (API + HTML fallback), Custom (HTML)
- Per-company scraper with semaphore-based concurrency control (5 simultaneous)
- Content-hash delta detection: jobs are only inserted if their hash doesn't match an existing active job
- URL deduplication: existing jobs with same company+URL are updated rather than duplicated
- LLM extraction service: OpenAI GPT-4o-mini for parsing raw job HTML into structured data (cost: ~$0.002/page)
- APScheduler integration: scrapes all companies every 3 hours (configurable via SCRAPE_INTERVAL_HOURS)
- Scraper API endpoints: POST /scraper/run (all), POST /scraper/run/{id} (single), GET /scraper/status
- Frontend Scraper page: run all/single, recent scrape history, ATS coverage breakdown
- 97 companies with ATS classification: 41 Lever, 17 Custom, 13 Greenhouse, 11 Workday, 9 Ashby, 5 iCIMS
- LLM extraction ready but off by default (requires OPENAI_API_KEY)
- Seniority inference from job titles
- User-Agent header for respectful scraping

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