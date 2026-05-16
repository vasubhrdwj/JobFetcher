import asyncio
import hashlib
import re
from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser

from app.models.models import Company


class BaseATSParser:
    ats_name: str = "custom"

    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> str | None:
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError:
            return None

    def content_hash(self, html: str) -> str:
        return hashlib.sha256(html.encode()).hexdigest()

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        raise NotImplementedError


class GreenhouseParser(BaseATSParser):
    ats_name = "greenhouse"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        board_token = self._extract_board_token(company.career_url)
        if not board_token:
            return []

        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return []

        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            location = job.get("location", {}).get("name", "")
            job_type = ""
            seniority = ""
            description = job.get("content", "") or ""
            departments = job.get("departments", [])
            department_name = departments[0].get("name", "") if departments else ""

            if description:
                description = re.sub(r"<[^>]+>", "", description)

            seniority = self._infer_seniority(title)
            is_remote = "remote" in location.lower() if location else False
            salary_min = job.get("salary_range", {}).get("min") if job.get("salary_range") else None
            salary_max = job.get("salary_range", {}).get("max") if job.get("salary_range") else None

            requirements = {}
            if departments:
                requirements["department"] = department_name

            jobs.append({
                "title": title,
                "url": f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job.get('id')}",
                "location": location,
                "job_type": job_type,
                "seniority": seniority,
                "description": description[:5000] if description else None,
                "requirements": requirements or None,
                "is_remote": is_remote,
                "salary_min": int(salary_min) if salary_min else None,
                "salary_max": int(salary_max) if salary_max else None,
                "source": "greenhouse",
                "posted_at": job.get("updated_at"),
                "content_hash": self.content_hash(f"{title}{location}{description[:500]}"),
            })
        return jobs

    def _extract_board_token(self, url: str) -> str | None:
        patterns = [
            r"greenhouse\.io/v1/boards/([^/]+)",
            r"boards\.greenhouse\.io/([^/?#]+)",
            r"careers.*greenhouse",
        ]
        for pattern in patterns[-1:]:
            match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
            if match:
                return match.group(1)
        return url.rstrip("/").split("/")[-1].split("?")[0]


class LeverParser(BaseATSParser):
    ats_name = "lever"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        slug = self._extract_slug(company.career_url)

        if slug and slug != "":
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return self._parse_api_jobs(data, slug)
            except (httpx.HTTPError, ValueError):
                pass

        return await self._parse_html_jobs(company, client)

    def _parse_api_jobs(self, data: list, slug: str) -> list[dict]:
        jobs = []
        for posting in data:
            title = posting.get("text", "")
            categories = posting.get("categories", {})
            location = categories.get("location", "")
            department = categories.get("department", "")
            commitment = categories.get("commitment", "")
            description = posting.get("description", {}).get("plain", "") or posting.get("description", {}).get("html", "") or ""
            description = re.sub(r"<[^>]+>", "", description)

            is_remote = "remote" in location.lower() if location else False
            seniority = self._infer_seniority(title)

            jobs.append({
                "title": title,
                "url": posting.get("url", posting.get("applyUrl", "")),
                "location": location,
                "job_type": commitment,
                "seniority": seniority,
                "description": description[:5000] if description else None,
                "requirements": {"department": department} if department else None,
                "is_remote": is_remote,
                "salary_min": None,
                "salary_max": None,
                "source": "lever_api",
                "posted_at": posting.get("createdAt"),
                "content_hash": self.content_hash(f"{title}{location}{description[:500]}"),
            })
        return jobs

    async def _parse_html_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            text = link.text(strip=True)
            if not text or len(text) < 5 or text.lower() in seen:
                continue

            is_job = any(kw in href.lower() for kw in ["job", "career", "position", "opening", "role"]) or \
                     any(kw in text.lower() for kw in ["engineer", "developer", "designer", "manager", "lead", "senior", "staff", "principal", "analyst", "architect", "director"])

            if not is_job:
                continue

            seen.add(text.lower())

            if not href.startswith("http"):
                base = company.career_url.rstrip("/")
                href = base + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": self._infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "lever_html",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{href}"),
            })

        return jobs

    def _extract_slug(self, url: str) -> str | None:
        match = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
        if match:
            return match.group(1)
        match = re.search(r"lever\.co/([^/?#]+)", url)
        if match:
            return match.group(1)
        parts = url.rstrip("/").split("/")
        return parts[-1].split("?")[0] if parts else None


class WorkdayParser(BaseATSParser):
    ats_name = "workday"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen_titles = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            text = link.text(strip=True)
            if not text or len(text) < 5 or "job" not in href.lower() and "career" not in href.lower():
                continue
            if text.lower() in seen_titles:
                continue
            seen_titles.add(text.lower())

            if not href.startswith("http"):
                href = company.career_url.rstrip("/") + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": self._infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "workday",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{href}"),
            })

        return jobs


class ICIMSParser(BaseATSParser):
    ats_name = "icims"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            text = link.text(strip=True)
            if not text or "icims" not in href or text.lower() in seen:
                continue
            seen.add(text.lower())

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": self._infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "icims",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{href}"),
            })

        return jobs


class AshbyParser(BaseATSParser):
    ats_name = "ashby"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        slug = self._extract_slug(company.career_url)
        if not slug:
            return []

        url = f"https://www.ashbyhq.com/api/careers/{slug}?isPublished=true"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return self._fallback_parse(company, client)
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return self._fallback_parse(company, client)

        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            location = job.get("location", {})
            loc_str = location.get("name", "") if isinstance(location, dict) else str(location)

            jobs.append({
                "title": title,
                "url": f"https://www.ashbyhq.com/{slug}/{job.get('id', '')}",
                "location": loc_str or None,
                "job_type": None,
                "seniority": self._infer_seniority(title),
                "description": None,
                "requirements": None,
                "is_remote": "remote" in loc_str.lower() if loc_str else None,
                "salary_min": None,
                "salary_max": None,
                "source": "ashby",
                "posted_at": job.get("publishedAt"),
                "content_hash": self.content_hash(f"{title}{loc_str}"),
            })

        return jobs

    def _fallback_parse(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = asyncio.get_event_loop().run_until_complete(self.fetch_page(company.career_url, client))
        if not html:
            return []
        tree = HTMLParser(html)
        jobs = []
        seen = set()
        for link in tree.css("a[href]"):
            text = link.text(strip=True)
            href = link.attributes.get("href", "")
            if not text or text.lower() in seen or len(text) < 5:
                continue
            if "job" not in href.lower() and "career" not in href.lower() and "ashby" not in href.lower():
                continue
            seen.add(text.lower())
            jobs.append({
                "title": text,
                "url": href if href.startswith("http") else company.career_url.rstrip("/") + "/" + href.lstrip("/"),
                "location": None,
                "job_type": None,
                "seniority": self._infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "ashby",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{href}"),
            })
        return jobs

    def _extract_slug(self, url: str) -> str | None:
        match = re.search(r"ashbyhq\.com/([^/]+)", url)
        if match:
            return match.group(1)
        parts = url.rstrip("/").split("/")
        return parts[-1].split("?")[0] if parts else None


class CustomParser(BaseATSParser):
    ats_name = "custom"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()

        job_keywords = ["job", "career", "position", "opening", "role", "engineer", "developer", "designer", "manager", "lead", "senior", "staff", "principal"]

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            text = link.text(strip=True)
            if not text or len(text) < 5 or text.lower() in seen:
                continue

            href_lower = href.lower()
            text_lower = text.lower()
            is_job = any(kw in href_lower for kw in job_keywords) or any(kw in text_lower for kw in ["engineer", "developer", "designer", "manager", "lead", "senior", "staff", "principal", "analyst", "architect"])

            if not is_job:
                continue

            seen.add(text.lower())

            if not href.startswith("http"):
                base = company.career_url.rstrip("/")
                href = base + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": self._infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "custom",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{href}"),
            })

        return jobs


def _infer_seniority(title: str) -> str | None:
    t = title.lower()
    if any(w in t for w in ["staff", "distinguished", "fellow", "principal"]):
        return "staff"
    if any(w in t for w in ["senior", "sr.", "sr ", "lead"]):
        return "senior"
    if any(w in t for w in ["junior", "jr.", "jr ", "entry", "intern", "associate"]):
        return "junior"
    if any(w in t for w in ["manager", "director", "head", "vp", "vice president", "chief"]):
        return "management"
    if any(w in t for w in ["mid", "mid-level"]):
        return "mid"
    return "mid"


BaseATSParser._infer_seniority = staticmethod(_infer_seniority)