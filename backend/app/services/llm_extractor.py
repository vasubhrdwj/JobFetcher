import hashlib
import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a job posting parser. Extract structured data from the raw HTML/text of a job posting page.

Return a JSON object with these fields:
- title: string (job title)
- location: string or null (e.g. "San Francisco, CA" or "Remote")
- job_type: string or null (e.g. "Full-time", "Part-time", "Contract")
- seniority: string or null (e.g. "Senior", "Mid", "Junior", "Staff", "Management")
- description: string or null (cleaned job description, max 3000 chars)
- requirements: object or null with keys like "required_skills", "nice_to_have", "education", "experience_years"
- responsibilities: object or null with keys like "primary", "secondary"
- is_remote: boolean or null
- salary_min: integer or null (annual USD)
- salary_max: integer or null (annual USD)
- posted_at: string or null (ISO 8601 date if found)

If the page is not a job posting, return null.
If a field cannot be determined, set it to null.
Be concise. No explanations, just valid JSON."""


async def extract_job_with_llm(raw_html: str, url: str) -> dict | None:
    if not settings.OPENAI_API_KEY and not settings.ANTHROPIC_API_KEY:
        logger.warning("No LLM API key configured, skipping LLM extraction")
        return None

    truncated = raw_html[:15000] if len(raw_html) > 15000 else raw_html

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        if not client:
            return None

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": f"URL: {url}\n\nRaw content:\n{truncated}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1500,
        )

        content = response.choices[0].message.content
        if not content:
            return None

        data = json.loads(content)

        if data is None or not data.get("title"):
            return None

        result = {
            "title": data.get("title"),
            "location": data.get("location"),
            "job_type": data.get("job_type"),
            "seniority": data.get("seniority"),
            "description": data.get("description", "")[:5000] if data.get("description") else None,
            "requirements": data.get("requirements"),
            "responsibilities": data.get("responsibilities"),
            "is_remote": data.get("is_remote"),
            "salary_min": data.get("salary_min"),
            "salary_max": data.get("salary_max"),
            "posted_at": data.get("posted_at"),
            "source": "llm_extraction",
            "content_hash": hashlib.sha256(
                (data.get("title", "") + (data.get("description", "") or "")[:500]).encode()
            ).hexdigest(),
            "url": url,
        }

        return result

    except Exception as e:
        logger.error(f"LLM extraction failed for {url}: {e}")
        return None


async def extract_jobs_from_page(raw_html: str, url: str) -> list[dict]:
    result = await extract_job_with_llm(raw_html, url)
    if result:
        return [result]
    return []