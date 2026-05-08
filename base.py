import os
import re
import csv
import json
from datetime import datetime
from html import unescape
import requests
from groq import Groq

def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv()
api_key = os.getenv("GROQ_API_KEY", "").strip()
if not api_key:
    print(
        "Missing GROQ_API_KEY. Add it to a local .env file as GROQ_API_KEY=your_key and re-run.",
        flush=True,
    )
    raise SystemExit(1)

client = Groq(api_key=api_key)

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
    timeout=20,
)
jobs = resp.json()[1:]  # first item is a legal notice, skip it
print(f"Got {len(jobs)} jobs. Scoring first 20...\n")

# 3. Score one job

def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def infer_hard_cap(job):
    title = (job.get("position") or "").lower()
    desc = strip_html(job.get("description", "")).lower()
    text = f"{title}\n{desc}"

    non_eng_keywords = [
        "sales", "account", "accounting", "hr", "human resources", "marketing",
        "hospitality", "healthcare", "nurse", "operations", "customer success",
        "business development",
    ]
    if any(k in text for k in non_eng_keywords):
        return 3, "non-engineering role detected"

    if any(k in title for k in ["lead", "staff", "principal", "senior"]):
        return 5, "seniority title cap for ~1 year candidate"

    if re.search(r"\b([4-9]|[1-9]\d)\+?\s*(years|yrs)\b", text):
        return 6, "4+ years requirement cap"

    tags = [t.lower() for t in (job.get("tags") or [])]
    if any(x in text for x in ["node.js", "nodejs", "golang", "go "]) and "python" not in text:
        if "python" not in tags:
            return 6, "stack mismatch cap"

    return 10, ""


def enforce_hard_cap(job, score):
    if not isinstance(score, int):
        return score
    cap, _ = infer_hard_cap(job)
    return min(score, cap)


def extract_single_quote_phrase(text):
    if not text:
        return ""
    m = re.search(r"'([^']+)'", text)
    return (m.group(1).strip() if m else "")


def quote_exists_in_jd(job, reason):
    phrase = extract_single_quote_phrase(reason)
    if not phrase:
        return False
    jd = (
        f"{job.get('position','')} "
        f"{', '.join(job.get('tags', []))} "
        f"{strip_html(job.get('description',''))}"
    ).lower()
    return phrase.lower() in jd


def score_job(resume, job):
    job_text = (
        f"Title: {job.get('position','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Tags: {', '.join(job.get('tags', []))}\n"
        f"Description: {strip_html(job.get('description',''))[:3000]}"
    )
    prompt = f"""You are a strict resume-job fit scorer. Ground your analysis ONLY in the JD text — never invent requirements.

Think through silently before answering:
1. ROLE_TYPE: software engineering | non-engineering (sales, accounting, hospitality, HR, marketing, operations, healthcare, etc.) | adjacent (data, devops, support engineering, etc.)
2. SENIORITY: read the title and any "X+ years" line. Tag as: intern | junior (0-2 yrs) | mid (2-5 yrs) | senior (5+ yrs) | lead/staff/principal.
3. REQUIRED_SKILLS: list ONLY technologies actually named in the JD text. Do not assume.
4. RESUME_MATCH: which of those skills does the candidate's resume actually mention?

HARD CAPS (apply BEFORE rubric, override everything):
- Non-engineering role -> max 3.
- Lead / Staff / Principal / Senior in title for a ~1 yr candidate -> max 5.
- JD explicitly requires 4+ years for a ~1 yr candidate -> max 6.
- Stack mismatch (e.g. JD says Node.js/Go, candidate has Python) caps at 6 unless skills are clearly transferable.

After caps, rubric:
- 0-2: wrong field or no real skill overlap
- 3-4: adjacent, transferable but significant ramp-up
- 5-6: relevant role with mismatched seniority OR partial skills overlap
- 7-8: solid fit — most required skills present, seniority reasonable
- 9-10: excellent — core JD skills directly match, seniority aligns

Resume:
{resume}

Job:
{job_text}

Respond on ONE line in EXACTLY this format:
SCORE|REASON

REASON requirements:
- MUST include one short verbatim phrase from the JD in single quotes (e.g. 'requires 4+ years', 'Customer Success Manager', 'Outside Sales Representative').
- Under 25 words total.
- If you cannot find a JD phrase to quote, the score is 0.

Examples:
3|Sales role: 'Outside Sales Representative to expand market presence'; backend skills don't transfer.
6|'4+ years' required, candidate has ~1; Node.js/Go stack vs. Python — partial overlap only.
8|Backend SDE: 'design and evolve the data model'; FastAPI/Kafka/OAuth experience aligns well."""
    completion = client.chat.completions.create(
        model="qwen/qwen3-32b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
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
        score = int(m.group(1))
        reason = m.group(2).strip()
        if 0 <= score <= 10 and quote_exists_in_jd(job, reason):
            return enforce_hard_cap(job, score), reason
    # Fail closed on parse or evidence mismatch.
    return None, "(invalid scorer output)"

# 3b. Phase 2 — critic agent reviews Phase 1's score
def critic_review(resume, job, phase1_score, phase1_reason):
    job_text = (
        f"Title: {job.get('position','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Tags: {', '.join(job.get('tags', []))}\n"
        f"Description: {strip_html(job.get('description',''))[:3000]}"
    )
    prompt = f"""You are a critic reviewing another agent's resume-job fit score. Your job is to catch errors, not to rubber-stamp.

Phase 1 produced:
SCORE: {phase1_score}
REASON: {phase1_reason}

Independently re-check against the SAME rules Phase 1 used:

HARD CAPS (must apply BEFORE rubric):
- Non-engineering role (sales, accounting, HR, marketing, hospitality, healthcare, etc.) -> max 3.
- Lead / Staff / Principal / Senior title for a ~1 yr candidate -> max 5.
- JD explicitly requires 4+ years for a ~1 yr candidate -> max 6.
- Stack mismatch (JD names a stack candidate doesn't have, not clearly transferable) -> max 6.

Rubric after caps:
- 0-2 wrong field; 3-4 adjacent ramp-up; 5-6 partial fit / seniority gap; 7-8 solid; 9-10 excellent.

Look for these Phase 1 failure modes:
- Missed a hard cap (e.g. scored a sales role above 3).
- Quoted phrase doesn't actually appear in the JD, or quote is generic filler.
- Inflated score from keyword overlap without true skill match.
- Deflated score despite clear stack + seniority alignment.

Resume:
{resume}

Job:
{job_text}

Respond on ONE line in EXACTLY this format:
FINAL_SCORE|VERDICT|REASON

- FINAL_SCORE: integer 0-10 (your corrected score; equal to Phase 1 if you agree).
- VERDICT: AGREE only if ALL checks pass, else REVISED.
- REASON: under 25 words, must include one short verbatim JD phrase in single quotes. If revising, name the specific Phase 1 error.

Mandatory critic checks before AGREE:
1) Confirm quoted phrase appears in JD text verbatim.
2) Confirm FINAL_SCORE obeys hard caps.
3) Confirm FINAL_SCORE is within 1 point of valid Phase 1 score.
If any check fails, output REVISED.

Examples:
3|REVISED|Phase 1 missed non-eng cap: 'Outside Sales Representative' is sales, not engineering.
7|AGREE|'design and evolve the data model' — backend stack and seniority align.
5|REVISED|Phase 1 inflated; JD requires '5+ years' for a ~1 yr candidate."""
    completion = client.chat.completions.create(
        model="qwen/qwen3-32b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_completion_tokens=4096,
        top_p=0.95,
        reasoning_effort="default",
        stream=False,
    )
    text = (completion.choices[0].message.content or "").strip()
    last = text.strip().splitlines()[-1]
    m = re.match(r"\s*(\d+)\s*\|\s*(AGREE|REVISED)\s*\|\s*(.+)", last, re.IGNORECASE)
    if m:
        score = int(m.group(1))
        verdict = m.group(2).strip().upper()
        reason = m.group(3).strip()
        if 0 <= score <= 10 and quote_exists_in_jd(job, reason):
            return enforce_hard_cap(job, score), verdict, reason
    return None, "?", "(invalid critic output)"

# 4. Loop over jobs, score, and collect results
results = []
for i, job in enumerate(jobs[:20], 1):
    title = job.get("position", "?")
    company = job.get("company", "?")
    print(f"[{i}/20] scoring: {title} @ {company}...", flush=True)
    try:
        score, reason = score_job(RESUME, job)
    except Exception as e:
        score, reason = None, str(e)[:120]
    print(f"   P1 [{score}] → {reason}", flush=True)
    final, verdict, crit_reason = None, "?", "(skipped)"
    if isinstance(score, int):
        try:
            final, verdict, crit_reason = critic_review(RESUME, job, score, reason)
        except Exception as e:
            final, verdict, crit_reason = None, "?", str(e)[:120]
        # Anti-rubber-stamp safety: AGREE only if critic score stays near scorer.
        if verdict == "AGREE" and isinstance(final, int) and abs(final - score) > 1:
            verdict = "REVISED"
            crit_reason = f"critic self-corrected: AGREE invalid for score drift; '{job.get('position','')[:30]}'"
        print(f"   P2 [{final}] {verdict} → {crit_reason}\n", flush=True)
    else:
        print("", flush=True)
    results.append({
        "title": title,
        "company": company,
        "url": job.get("url") or job.get("apply_url") or "",
        "p1_score": score,
        "p2_score": final,
        "verdict": verdict,
        "reason": crit_reason if isinstance(final, int) else reason,
    })

# 5. Phase 3 — ranked top-N
TOP_N = 10
ranked = sorted(
    [r for r in results if isinstance(r["p2_score"], int)],
    key=lambda r: r["p2_score"],
    reverse=True,
)[:TOP_N]

print("=" * 72)
print(f"TOP {len(ranked)} MATCHES (ranked by Phase 2 score)")
print("=" * 72)
for rank, r in enumerate(ranked, 1):
    print(f"{rank:>2}. [{r['p2_score']}] {r['title']} @ {r['company']}")
    print(f"    {r['reason']}")
    if r["url"]:
        print(f"    {r['url']}")
    print()

# 6. Persist results
out_dir = "results"
os.makedirs(out_dir, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
json_path = os.path.join(out_dir, f"run_{stamp}.json")
csv_path = os.path.join(out_dir, f"run_{stamp}.csv")

with open(json_path, "w") as f:
    json.dump({"timestamp": stamp, "results": results}, f, indent=2)

fields = ["title", "company", "url", "p1_score", "p2_score", "verdict", "reason"]
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in results:
        w.writerow(r)

print(f"Saved {len(results)} results to {json_path} and {csv_path}")