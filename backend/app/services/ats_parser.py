import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.models.models import Company



_host_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_host_sem(url: str) -> asyncio.Semaphore:
    host = urlparse(url).netloc.lower()
    if host not in _host_semaphores:
        _host_semaphores[host] = asyncio.Semaphore(2)
    return _host_semaphores[host]

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
    "search again", "log back in", "again", "intro",
}

URL_BLACKLIST_PATTERNS = [
    re.compile(r"\.(pdf|doc|docx|png|jpg|jpeg|svg|gif|mp4|mp3|zip)$", re.I),
    re.compile(r"(youtube\.com|youtu\.be|twitter\.com|x\.com|linkedin\.com|github\.com|medium\.com|facebook\.com|instagram\.com)", re.I),
    re.compile(r"^mailto:", re.I),
    re.compile(r"^javascript:", re.I),
    re.compile(r"/feed(/|$)", re.I),
    re.compile(r"/jobs/(intro|login)(/|$|\?)", re.I),
]

def _clean_title(raw: str) -> str:
    t = raw.strip()
    t = re.sub(r"^Title\s+", "", t)
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (429, 502, 503, 504)),
           reraise=True)
    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> str | None:
        sem = _get_host_sem(url)
        async with sem:
            try:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 502, 503, 504):
                    raise
                return None
            except httpx.HTTPError:
                return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (429, 502, 503, 504)),
           reraise=True)
    async def fetch_json(self, url: str, client: httpx.AsyncClient, method: str = "GET", json_body: dict | None = None) -> dict | list | None:
        sem = _get_host_sem(url)
        async with sem:
            try:
                if method.upper() == "POST":
                    resp = await client.post(url, json=json_body, headers={"Content-Type": "application/json"}, follow_redirects=True)
                else:
                    resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (429, 502, 503, 504):
                    raise
                return None
            except (httpx.HTTPError, ValueError):
                return None

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        raise NotImplementedError


class GreenhouseParser(BaseATSParser):
    ats_name = "greenhouse"

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        token = company.ats_slug or self._extract_board_token(company.career_url, company.name)
        if not token:
            return []

        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        data = await self.fetch_json(url, client)
        if not data or not isinstance(data, dict):
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
                "posted_at": job.get("first_published") or job.get("updated_at"),
                "content_hash": self.content_hash(f"{title}{location}{(description or '')[:1000]}"),
            })
        return jobs

    def _extract_board_token(self, url: str, company_name: str | None = None) -> str | None:
        match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
        if match:
            return match.group(1)
        match = re.search(r"greenhouse\.io/v1/boards/([^/?#]+)", url)
        if match:
            return match.group(1)
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
        slug = company.ats_slug or self._extract_slug(company.career_url)
        if slug:
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            data = await self.fetch_json(url, client)
            if data and isinstance(data, list) and len(data) > 0:
                return self._parse_api_jobs(data)

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

            posted_at = posting.get("createdAt")
            if isinstance(posted_at, (int, float)):
                posted_at = datetime.fromtimestamp(posted_at / 1000, tz=timezone.utc).isoformat()

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
                "posted_at": posted_at,
                "content_hash": self.content_hash(f"{title}{location}{description[:1000]}"),
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

    def _extract_cxs_parts(self, url: str, company_name: str | None = None) -> tuple[str, str] | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.strip("/")
        match = re.match(r"((?:[\w-]+\.wd\d+\.myworkdayjobs\.com)|(?:[\w-]+\.myworkdayjobs\.com))", host)
        if not match:
            return None
        tenant_host = match.group(1)
        parts = path.strip("/").split("/")
        site = parts[0] if parts else None
        if not site:
            slug = company_name.lower().replace(" ", "").replace("-", "") if company_name else None
            site = slug
        if not site:
            return None
        return (tenant_host, site)

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        slug = company.ats_slug if company.ats_slug else None
        if slug:
            parts = slug.split("/", 1) if "/" in slug else None
            if parts and len(parts) == 2:
                cxs_url = f"https://{parts[0]}/wday/cxs/{parts[0].split('.')[0]}/{parts[1]}/jobs"
                result = await self._fetch_cxs_jobs(cxs_url, client)
                if result is not None:
                    return result

        cxs_parts = self._extract_cxs_parts(company.career_url, company.name)
        if cxs_parts:
            tenant_host, site = cxs_parts
            tenant = tenant_host.split(".")[0]
            cxs_url = f"https://{tenant_host}/wday/cxs/{tenant}/{site}/jobs"
            result = await self._fetch_cxs_jobs(cxs_url, client)
            if result is not None:
                return result

        return await self._parse_html_jobs(company, client)

    async def _fetch_cxs_jobs(self, cxs_url: str, client: httpx.AsyncClient) -> list[dict] | None:
        all_jobs = []
        offset = 0
        limit = 20
        while True:
            try:
                data = await self.fetch_json(
                    cxs_url, client, method="POST",
                    json_body={"limit": limit, "offset": offset, "searchText": ""},
                )
                if not data:
                    return None if offset == 0 else all_jobs
            except Exception:
                return None if offset == 0 else all_jobs

            page_jobs, should_break = self._parse_cxs_page(data, cxs_url, offset)
            all_jobs.extend(page_jobs)

            total = data.get("total", 0)
            offset += limit
            if should_break or offset >= total or offset >= 500:
                break

        return all_jobs if all_jobs else (None if offset == limit else all_jobs)

    def _parse_cxs_page(self, data: dict, cxs_url: str, offset: int) -> tuple[list[dict], bool]:
        job_list = data.get("jobPostings") or []
        if not job_list:
            return [], True

        base_host = urlparse(cxs_url).netloc
        jobs = []
        for job in job_list:
            title = (job.get("title") or "").strip()
            if not title:
                continue
            ext_path = job.get("externalPath", "")
            url = ext_path if ext_path.startswith("http") else f"https://{base_host}{ext_path}"
            location = job.get("locationsText", "")
            posted_on = job.get("postedOn", "")

            jobs.append({
                "title": title,
                "url": url,
                "location": location or None,
                "job_type": None,
                "seniority": _infer_seniority(title),
                "description": None,
                "requirements": None,
                "is_remote": "remote" in location.lower() if location else None,
                "salary_min": None,
                "salary_max": None,
                "source": "workday",
                "posted_at": posted_on or None,
                "content_hash": self.content_hash(f"{title}{url}"),
            })
        return jobs, False

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


def _add_params(url: str, params: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{params}"


class ICIMSParser(BaseATSParser):
    ats_name = "icims"

    # NOTE: JSON and RSS endpoints are best-effort; most iCIMS tenants return
    # HTML for all format params. HTML fallback is the only path smoke-tested
    # against a real tenant (General Dynamics / careers-gdms.icims.com).

    async def parse_jobs(self, company: Company, client: httpx.AsyncClient) -> list[dict]:
        base_url = company.career_url.rstrip("/")

        json_url = _add_params(base_url, "in_iframe=1&format=json")
        data = await self.fetch_json(json_url, client)
        if data and isinstance(data, list) and len(data) > 0:
            return self._parse_json_jobs(data, base_url)

        rss_url = _add_params(base_url, "in_iframe=1&format=rss")
        rss_text = await self.fetch_page(rss_url, client)
        if rss_text and "rss" in rss_text.lower()[:500]:
            return self._parse_rss_jobs(rss_text, base_url)

        return await self._parse_html_jobs(company, client)

    def _parse_json_jobs(self, data: list, base_url: str) -> list[dict]:
        jobs = []
        seen = set()
        for item in data:
            title = (item.get("title") or item.get("position") or "").strip()
            if not title:
                continue
            url = item.get("url") or item.get("link") or ""
            if not url and item.get("id"):
                url = _add_params(base_url, f"jobId={item['id']}")
            if not url:
                continue
            text = _clean_title(title)
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            location = item.get("location") or item.get("city") or ""
            jobs.append({
                "title": text,
                "url": url,
                "location": location or None,
                "job_type": None,
                "seniority": _infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": "remote" in location.lower() if location else None,
                "salary_min": None,
                "salary_max": None,
                "source": "icims_json",
                "posted_at": item.get("posted_date") or item.get("created_date"),
                "content_hash": self.content_hash(f"{text}{url}"),
            })
        return jobs

    def _parse_rss_jobs(self, rss_text: str, base_url: str) -> list[dict]:
        jobs = []
        seen = set()
        try:
            root = ET.fromstring(rss_text)
        except ET.ParseError:
            return []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            text = _clean_title(title)
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            location = item.findtext("location") or ""
            jobs.append({
                "title": text,
                "url": link,
                "location": location or None,
                "job_type": None,
                "seniority": _infer_seniority(text),
                "description": None,
                "requirements": None,
                "is_remote": "remote" in location.lower() if location else None,
                "salary_min": None,
                "salary_max": None,
                "source": "icims_rss",
                "posted_at": item.findtext("pubDate"),
                "content_hash": self.content_hash(f"{text}{link}"),
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
        slug = company.ats_slug or self._extract_slug(company.career_url)
        if slug:
            url = f"https://www.ashbyhq.com/api/careers/{slug}?isPublished=true"
            data = await self.fetch_json(url, client)
            if data and isinstance(data, dict) and "jobs" in data:
                return self._parse_api_jobs(data, slug)

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

        if len(jobs) < 3:
            from app.config import settings
            if settings.LLM_FALLBACK_ENABLED and settings.OPENAI_API_KEY:
                from app.services.llm_extractor import extract_job_links_from_page
                llm_jobs = await extract_job_links_from_page(html, company.career_url)
                for j in llm_jobs:
                    if j.get("title", "").lower() not in seen:
                        jobs.append(j)
                        seen.add(j.get("title", "").lower())

        return jobs


ATS_PARSERS: dict[str, BaseATSParser] = {
    "greenhouse": GreenhouseParser(),
    "lever": LeverParser(),
    "workday": WorkdayParser(),
    "icims": ICIMSParser(),
    "ashby": AshbyParser(),
    "custom": CustomParser(),
}