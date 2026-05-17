import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser

from app.models.models import Company

logger = logging.getLogger(__name__)

NAV_BLACKLIST = {
    "see open positions", "explore our teams", "see our process",
    "join our community", "learn more", "careers", "all jobs",
    "view all jobs", "see all jobs", "back to careers", "home",
    "search jobs", "filter jobs", "life at", "working at",
    "benefits", "diversity", "culture", "values", "hiring process",
    "about us", "about", "contact us", "contact", "sign in", "log in",
    "apply now", "intern", "internship program", "university recruiting",
    "cookie", "privacy policy", "privacy", "terms of use", "terms",
    "accessibility", "status", "enterprise", "startups", "community",
    "pricing", "customers", "sign up", "login", "open app",
    " readme", "docs", "documentation", "support", "help", "faq",
    "blog", "press", "news", "resources", "download", "changelog",
    "security", "trust", "leadership", "team", "mission", "investors",
    "partners", "api docs", "developers", "sdk", "integrations",
    "methodology", "overview", "features", "product", "platform",
    "solutions", "services", "use cases", "case studies", "testimonials",
    "webinars", "events", "podcast", "newsletter", "careers home",
    "search", "menu", "skip to content", "toggle", "close",
}

URL_BLACKLIST_PATTERNS = [
    re.compile(r"\.(pdf|doc|docx|png|jpg|jpeg|svg|gif|mp4|mp3|zip)$", re.I),
    re.compile(r"(youtube\.com|youtu\.be|twitter\.com|x\.com|linkedin\.com|github\.com|medium\.com|facebook\.com|instagram\.com)", re.I),
    re.compile(r"^mailto:", re.I),
    re.compile(r"^javascript:", re.I),
    re.compile(r"/feed(/|$)", re.I),
]

def _clean_title(raw: str) -> str:
    t = raw.strip()
    t = re.sub(r"\s+", " ", t)

    TRAILING_NOISE = re.compile(
        r"\s*(?:"
        r"[-–—]?\s*(?:Full-?time|Part-?time|Contract|Permanent|Remote|On-?site|Hybrid)"
        r"|Learn more.?"
        r"|(?:,\s*)?(?:APAC|EMEA|LATAM|AMER|North America|South America|Europe|Asia Pacific|United States|United Kingdom|UK|US|Global)"
        r"|(?:,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)+$"
        r")", re.I)
    t = TRAILING_NOISE.sub("", t)

    TRAILING_LOCATIONS = [
        re.compile(r"Tel Aviv[- ]?Yafo$", re.I),
        re.compile(r"New York$", re.I),
        re.compile(r"San Francisco$", re.I),
        re.compile(r"London$", re.I),
        re.compile(r"Berlin$", re.I),
        re.compile(r"Remote\.?$", re.I),
        re.compile(r"Australia$", re.I),
        re.compile(r"Singapore$", re.I),
        re.compile(r"Amsterdam$", re.I),
        re.compile(r"Toronto$", re.I),
    ]
    for pat in TRAILING_LOCATIONS:
        t = pat.sub("", t)

    TITLE_NOISE = [
        re.compile(r"Full-?time", re.I),
        re.compile(r"Part-?time", re.I),
        re.compile(r"Contract", re.I),
        re.compile(r"Permanent", re.I),
        re.compile(r"\bRemote\b", re.I),
        re.compile(r"On-?site", re.I),
        re.compile(r"Hybrid", re.I),
        re.compile(r"Learn more.?", re.I),
        re.compile(r"\s*\(.*?\)\s*$"),
    ]
    for pat in TITLE_NOISE:
        t = pat.sub("", t)

    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*[-–—,]\s*$", "", t).strip()
    t = re.sub(r"\s*\(\s*\)\s*$", "", t).strip()

    ICON_NOISE = re.compile(r"(\w{3,}?)\1+", re.I)
    m = ICON_NOISE.search(t)
    if m:
        word = m.group(1)
        if len(word) <= 20:
            t = ICON_NOISE.sub(r"\1", t)

    t = re.sub(r"(?:work_outline|search|close|menu|arrow_\w+|more_\w+|chevron_\w+|expand_\w+)", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*[-–—,]\s*$", "", t).strip()

    if len(t) < 5:
        return ""
    return t


def _is_valid_job_link(href: str, text: str, company_url: str) -> bool:
    href_lower = href.lower().split("?")[0].split("#")[0]
    text_lower = text.lower().strip()
    if len(text) < 8:
        return False
    if text_lower in NAV_BLACKLIST:
        return False
    for pat in URL_BLACKLIST_PATTERNS:
        if pat.search(href_lower):
            return False
    if href_lower.startswith(("#", "javascript:", "mailto:")) or href_lower in ("", "/"):
        return False
    base = company_url.lower().rstrip("/")
    if href_lower.rstrip("/") == base or href_lower.rstrip("/") == base + "/careers":
        return False
    NAV_PATHS = {"/privacy", "/terms", "/legal", "/about", "/contact", "/press", "/blog", "/docs", "/support", "/help", "/pricing", "/security", "/trust", "/changelog", "/status", "/community", "/customers", "/enterprise", "/resources", "/methodology", "/features", "/platform", "/solutions", "/services", "/login", "/signup", "/sign-up", "/sign-in"}
    try:
        from urllib.parse import urlparse
        path = urlparse(href_lower).path.rstrip("/")
        if path in NAV_PATHS:
            return False
    except Exception:
        pass
    JOB_KEYWORDS = ["engineer", "developer", "designer", "manager", "analyst", "scientist", "architect", "lead", "director", "specialist", "coordinator", "recruiter", "operator", "intern", "associate", "consultant", "advocate", "strategist", "planner", "accountant", "administrator", "technician", "writer", "editor", "researcher", "head", "vp", "president", "officer", "executive", "product", "data", "infrastructure", "reliability", "frontend", "backend", "fullstack", "full-stack", "mobile", "devops", "sre", "qa", "test"]
    if any(kw in text_lower for kw in JOB_KEYWORDS):
        return True
    if any(kw in href_lower for kw in ("/job/", "/jobs/", "/position/", "/opening/", "/role/", "/apply", "/posting/")):
        return True
    if re.search(r"/\d{4,}/?", href_lower):
        return True
    if href_lower.startswith(base):
        remainder = href_lower[len(base):].strip("/")
        parts = remainder.strip("/").split("/")
        if len(parts) >= 2 and len(remainder) > 15:
            return True
    return False


def _infer_seniority(title: str) -> str | None:
    t = title.lower()
    if any(w in t for w in ["distinguished", "fellow", "principal"]):
        return "staff"
    if any(w in t for w in ["senior", "sr.", "sr ", "lead"]):
        return "senior"
    if any(w in t for w in ["junior", "jr.", "jr ", "entry", "intern", "associate"]):
        return "junior"
    if any(w in t for w in ["manager", "director", "head ", "vp ", "vice president", "chief"]):
        return "management"
    return "mid"


class BaseATSParser:
    ats_name: str = "custom"

    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> str | None:
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError:
            return None

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        raise NotImplementedError


class GreenhouseParser(BaseATSParser):
    ats_name = "greenhouse"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        token = self._extract_board_token(company.career_url, company.name)
        if not token:
            return []

        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return []

        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            if not title:
                continue
            location = job.get("location", {}).get("name", "")
            description = job.get("content", "") or ""
            if description:
                description = re.sub(r"<[^>]+>", "", description)[:5000]
            departments = job.get("departments", [])
            department_name = departments[0].get("name", "") if departments else ""
            salary_range = job.get("salary_range") or {}
            salary_min = salary_range.get("min")
            salary_max = salary_range.get("max")

            jobs.append({
                "title": title.strip(),
                "url": f"https://boards.greenhouse.io/{token}/jobs/{job.get('id')}",
                "location": location or None,
                "job_type": None,
                "seniority": _infer_seniority(title),
                "description": description or None,
                "requirements": {"department": department_name} if department_name else None,
                "is_remote": "remote" in location.lower() if location else None,
                "salary_min": int(salary_min) if salary_min else None,
                "salary_max": int(salary_max) if salary_max else None,
                "source": "greenhouse",
                "posted_at": job.get("updated_at"),
                "content_hash": self.content_hash(f"{title}{location}"),
            })
        return jobs

    def _extract_board_token(self, url: str, company_name: str | None = None) -> str | None:
        match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
        if match:
            return match.group(1)
        match = re.search(r"greenhouse\.io/v1/boards/([^/?#]+)", url)
        if match:
            return match.group(1)
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().replace("www.", "")
        parts = domain.split(".")
        slug = parts[0] if parts else None
        if slug in ("about", "careers", "jobs", "www", "boards"):
            if len(parts) > 1:
                slug = parts[1] if parts[1] not in ("com", "io", "co", "org", "net") else parts[0]
            elif company_name:
                slug = company_name.lower().replace(" ", "").replace("-", "")
        if slug and slug not in ("about", "careers", "jobs", "www", "boards"):
            return slug
        if company_name:
            return company_name.lower().replace(" ", "").replace("-", "")
        return None


class LeverParser(BaseATSParser):
    ats_name = "lever"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        slug = self._extract_slug(company.career_url)
        if slug:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return self._parse_api_jobs(data)
            except (httpx.HTTPError, ValueError):
                pass

        return await self._parse_html_jobs(company, client)

    def _parse_api_jobs(self, data: list) -> list[dict]:
        jobs = []
        for posting in data:
            title = posting.get("text", "").strip()
            if not title:
                continue
            categories = posting.get("categories", {})
            location = categories.get("location", "")
            department = categories.get("department", "")
            commitment = categories.get("commitment", "")
            description = ""
            desc_obj = posting.get("description", {})
            if isinstance(desc_obj, dict):
                description = desc_obj.get("plain", "") or desc_obj.get("html", "") or ""
            description = re.sub(r"<[^>]+>", "", description)[:5000]

            apply_url = posting.get("url") or posting.get("applyUrl") or ""

            jobs.append({
                "title": title,
                "url": apply_url,
                "location": location or None,
                "job_type": commitment or None,
                "seniority": _infer_seniority(title),
                "description": description or None,
                "requirements": {"department": department} if department else None,
                "is_remote": "remote" in location.lower() if location else None,
                "salary_min": None,
                "salary_max": None,
                "source": "lever_api",
                "posted_at": posting.get("createdAt"),
                "content_hash": self.content_hash(f"{title}{location}"),
            })
        return jobs

    async def _parse_html_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        postings_url = company.career_url.rstrip("/")
        if not postings_url.endswith("/"):
            postings_url += "/"

        for suffix in ["#careers", "?department=&team=&location="]:
            test_url = postings_url.rstrip("/") + suffix
            test_html = await self.fetch_page(test_url, client)
            if test_html and len(test_html) > len(html) * 0.8:
                html = test_html
                break

        tree = HTMLParser(html)
        jobs = []
        seen = set()
        base = company.career_url.rstrip("/")

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            raw_text = link.text(strip=True)
            if not raw_text or len(raw_text) < 5:
                continue
            text = _clean_title(raw_text)
            if not text or text.lower() in seen:
                continue
            if not _is_valid_job_link(href, text, base):
                continue

            if text.lower() in NAV_BLACKLIST:
                continue

            seen.add(text.lower())

            if not href.startswith("http"):
                href = base + "/" + href.lstrip("/")

            if re.search(r"/\d{4,}/?$", href):
                pass
            elif any(kw in href.lower() for kw in ["job=", "jid=", "gh_jid=", "lever", "greenhouse"]):
                pass
            elif any(kw in text.lower() for kw in ["engineer", "developer", "designer", "manager", "director", "lead", "senior", "staff", "principal", "architect", "analyst", "scientist", "programmer"]):
                pass
            else:
                continue

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": _infer_seniority(text),
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
        if "lever" not in url.lower():
            return None
        return None


class WorkdayParser(BaseATSParser):
    ats_name = "workday"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()
        base = company.career_url.rstrip("/")

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            raw_text = link.text(strip=True)

            if not _is_valid_job_link(href, raw_text, base):
                continue

            text = _clean_title(raw_text)
            if not text or text.lower() in seen:
                continue

            if text.lower() in NAV_BLACKLIST:
                continue

            has_job_url = any(kw in href.lower() for kw in ["/job/", "/jobs/", "/jcsr/", "/facet", "wd5=", "wd/job/", "jobid=", "reqid="])
            if not has_job_url:
                title_keywords = ["engineer", "developer", "designer", "manager", "lead", "senior", "staff", "principal", "analyst", "architect", "director", "scientist", "program manager", "product manager"]
                if not any(kw in text.lower() for kw in title_keywords):
                    continue

            seen.add(text.lower())

            if not href.startswith("http"):
                href = base + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": _infer_seniority(text),
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
        base = company.career_url.rstrip("/")

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            if "icims" not in href.lower():
                continue

            raw_text = link.text(strip=True)
            if not _is_valid_job_link(href, raw_text, base):
                continue

            text = _clean_title(raw_text)
            if not text or text.lower() in seen:
                continue

            seen.add(text.lower())

            jobs.append({
                "title": text,
                "url": href,
                "location": None,
                "job_type": None,
                "seniority": _infer_seniority(text),
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
        if slug:
            url = f"https://www.ashbyhq.com/api/careers/{slug}?isPublished=true"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "jobs" in data:
                        return self._parse_api_jobs(data, slug)
            except (httpx.HTTPError, ValueError):
                pass

        return await self._parse_html_jobs(company, client)

    def _parse_api_jobs(self, data: dict, slug: str) -> list[dict]:
        jobs = []
        for job in data.get("jobs", []):
            title = job.get("title", "").strip()
            if not title:
                continue
            location = job.get("location", {})
            loc_str = location.get("name", "") if isinstance(location, dict) else str(location)

            jobs.append({
                "title": title,
                "url": f"https://www.ashbyhq.com/{slug}/{job.get('id', '')}",
                "location": loc_str or None,
                "job_type": None,
                "seniority": _infer_seniority(title),
                "description": None,
                "requirements": None,
                "is_remote": "remote" in loc_str.lower() if loc_str else None,
                "salary_min": None,
                "salary_max": None,
                "source": "ashby_api",
                "posted_at": job.get("publishedAt"),
                "content_hash": self.content_hash(f"{title}{loc_str}"),
            })
        return jobs

    async def _parse_html_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()
        base = company.career_url.rstrip("/")

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")

            left_div = link.css_first("[class*='rowLeft']")
            right_div = link.css_first("[class*='rowRight']")
            if left_div:
                raw_text = left_div.text(strip=True)
                location_text = right_div.text(strip=True) if right_div else None
                location_text = re.sub(r"Learn more.?", "", location_text, flags=re.I).strip() if location_text else None
            else:
                raw_text = link.text(strip=True)
                location_text = None

            if not _is_valid_job_link(href, raw_text, base):
                continue

            text = _clean_title(raw_text)
            if not text or text.lower() in seen:
                continue

            if text.lower() in NAV_BLACKLIST:
                continue

            seen.add(text.lower())

            if href.startswith("http"):
                url = href
            else:
                url = base + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": url,
                "location": location_text,
                "job_type": None,
                "seniority": _infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "ashby_html",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{url}"),
            })

        return jobs

    def _extract_slug(self, url: str) -> str | None:
        match = re.search(r"ashbyhq\.com/([^/]+)", url)
        if match:
            return match.group(1)
        return None


class CustomParser(BaseATSParser):
    ats_name = "custom"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        html = await self.fetch_page(company.career_url, client)
        if not html:
            return []

        tree = HTMLParser(html)
        jobs = []
        seen = set()
        base = company.career_url.rstrip("/")

        title_keywords = [
            "engineer", "developer", "designer", "manager", "lead",
            "senior", "staff", "principal", "analyst", "architect",
            "director", "scientist", "program manager", "product manager",
            "head of", "vp of", "chief", "intern",
        ]

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            raw_text = link.text(strip=True)

            if not _is_valid_job_link(href, raw_text, base):
                continue

            text = _clean_title(raw_text)
            if not text or text.lower() in seen:
                continue

            if text.lower() in NAV_BLACKLIST:
                continue

            is_specific = (
                re.search(r"/\d{4,}/?$", href) or
                any(kw in href.lower() for kw in ["/job/", "/jobs/", "jobid=", "reqid=", "gh_jid=", "jid=", "#job"]) or
                any(kw in text.lower() for kw in title_keywords)
            )

            if not is_specific:
                continue

            seen.add(text.lower())

            if href.startswith("http"):
                url = href
            else:
                url = base + "/" + href.lstrip("/")

            jobs.append({
                "title": text,
                "url": url,
                "location": None,
                "job_type": None,
                "seniority": _infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": None,
                "salary_min": None,
                "salary_max": None,
                "source": "custom",
                "posted_at": None,
                "content_hash": self.content_hash(f"{text}{url}"),
            })

        return jobs


ATS_PARSERS: dict[str, BaseATSParser] = {
    "greenhouse": GreenhouseParser(),
    "lever": LeverParser(),
    "workday": WorkdayParser(),
    "icims": ICIMSParser(),
    "ashby": AshbyParser(),
    "custom": CustomParser(),
}