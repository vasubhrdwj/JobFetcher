import os
import re
from html import unescape
import requests
from groq import Groq

client = Groq()  # reads GROQ_API_KEY from env var

# 1. Your resume — paste a short version, or load from a file
RESUME = """
Vasu Bhardwaj — Software Engineer

Profile:
Software Development Engineer with experience designing secure, enterprise-grade
microservices and event-driven architectures. Expertise in identity lifecycles
(SCIM 2.0), OAuth/OIDC security flows, and high-throughput REST APIs. Strong
algorithmic foundation — LeetCode Knight, rating 1878.

Experience:
- Software Engineer, Zenarate
  * Designed and deployed a SCIM 2.0 identity provisioning microservice integrating
    Azure AD and Okta; reduced onboarding time by 40%.
  * Built an event-driven ingestion pipeline using Kafka and AWS Lambda processing
    250+ TPS, OAuth-secured service communication for xAPI analytics.
- Intern, Eduskills - UiPath
  * Built UiPath bots automating data entry workflows; reduced processing time 60%.

Education:
B.Tech in Computer Science & Engineering, KIIT (Kalinga Institute of Industrial
Technology), 2021–2025. CGPA: 8.86/10. Coursework: OS, Cloud, Computer Networks,
Neural Networks, OOP.

Projects:
- Decentralized Lottery — Solidity, Hardhat, Ethereum, Chainlink, Next.js, Node.js,
  MetaMask integration.
- Distributed Task Orchestration Engine — FastAPI + Docker; JWT auth with refresh
  token rotation; normalized 3NF schema; SQLAlchemy with indexing/pooling; Docker
  Compose multi-container with FastAPI + MySQL.

Skills:
- Languages: Python, C++, JavaScript, SQL
- Backend & Security: FastAPI, Node.js, REST APIs, Microservices, Event-Driven
  Architecture, OAuth 2.0, OIDC, SCIM
- Databases & Infrastructure: PostgreSQL, MySQL, Kafka, Docker, AWS, Linux, Git
- Core CS: DSA, Object-Oriented Design

Certifications:
- Microsoft Certified: Azure AI Fundamentals (Jan 2024)
- AWS Academy Graduate — Introduction to Cloud
"""
# Or: RESUME = open("resume.txt").read()

# 2. Fetch jobs from RemoteOK (free, no auth)
print("Fetching jobs...")
resp = requests.get(
    "https://remoteok.com/api",
    headers={"User-Agent": "learning-script"},
)
jobs = resp.json()[1:]  # first item is a legal notice, skip it
print(f"Got {len(jobs)} jobs. Scoring first 20...\n")

# 3. Score one job

def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def score_job(resume, job):
    job_text = (
        f"Title: {job.get('position','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Tags: {', '.join(job.get('tags', []))}\n"
        f"Description: {strip_html(job.get('description',''))[:3000]}"
    )
    prompt = f"""You score how well a candidate's resume fits a job posting.

Rubric (skills overlap matters more than seniority match):
- 0-2: clearly wrong field (sales, accounting, healthcare, etc.) OR requires skills the candidate doesn't have at all.
- 3-4: adjacent field, some transferable skills, would need significant ramp-up.
- 5-6: relevant role but mismatched seniority (e.g. asks for 5+ yrs, candidate has 1) OR partial skills overlap.
- 7-8: solid fit — candidate has most required skills, seniority is reasonable, would be a strong applicant.
- 9-10: excellent fit — candidate's core skills directly match the JD, seniority aligns, would likely get an interview.

A backend/SDE role asking for Python, FastAPI, REST, microservices, OAuth, Kafka, Docker, AWS — even at "Software Engineer II" level — should score 7+ for this candidate.

Resume:
{resume}

Job:
{job_text}

Respond in EXACTLY this format on one line:
SCORE|REASON
where SCORE is an integer 0-10 and REASON is one short sentence (under 20 words).
Example: 7|Strong backend skills match, but JD asks for 3+ yrs Kafka in production."""
    completion = client.chat.completions.create(
        model="qwen/qwen3-32b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,        # lower = more consistent scoring
        max_completion_tokens=4096,
        top_p=0.95,
        reasoning_effort="default",
        stream=False,
    )
    text = (completion.choices[0].message.content or "").strip()
    # print(f"   RAW: {repr(text)[:200]}", flush=True)
    # parse "SCORE|REASON" — grab last line in case model adds preamble
    last = text.strip().splitlines()[-1]
    m = re.match(r"\s*(\d+)\s*\|\s*(.+)", last)
    if m:
        return int(m.group(1)), m.group(2).strip()
    # fallback: any 0-10 number
    n = re.search(r"\b(10|[0-9])\b", text)
    return (int(n.group(1)) if n else None), "(no reason parsed)"

# 4. Loop over jobs and print scores
for i, job in enumerate(jobs[:20], 1):
    title = job.get("position", "?")
    company = job.get("company", "?")
    print(f"[{i}/20] scoring: {title} @ {company}...", flush=True)
    try:
        score, reason = score_job(RESUME, job)
    except Exception as e:
        score, reason = "err", str(e)[:120]
    print(f"   [{score}] → {reason}\n", flush=True)