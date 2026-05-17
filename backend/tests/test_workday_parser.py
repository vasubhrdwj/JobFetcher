import pytest
from app.services.ats_parser import WorkdayParser
from app.models.models import Company, ATSPlatform


def test_cxs_page_parsing():
    parser = WorkdayParser()

    data = {
        "jobPostings": [
            {
                "title": "Senior Software Engineer",
                "externalPath": "/en-US/jobs/12345",
                "locationsText": "San Francisco, CA",
                "postedOn": "2024-01-15",
            },
            {
                "title": "Product Manager",
                "externalPath": "/en-US/jobs/67890",
                "locationsText": "Remote",
                "postedOn": "2024-01-10",
            },
        ],
        "total": 2,
    }

    cxs_url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/acme/jobs"
    jobs, done = parser._parse_cxs_page(data, cxs_url, 0)

    assert len(jobs) == 2
    assert jobs[0]["title"] == "Senior Software Engineer"
    assert jobs[0]["url"] == "https://acme.wd5.myworkdayjobs.com/en-US/jobs/12345"
    assert jobs[0]["location"] == "San Francisco, CA"
    assert jobs[0]["source"] == "workday"
    assert jobs[1]["title"] == "Product Manager"
    assert jobs[1]["url"] == "https://acme.wd5.myworkdayjobs.com/en-US/jobs/67890"


def test_cxs_url_no_double_protocol():
    from urllib.parse import urlparse

    cxs_url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/acme/jobs"
    ext_path = "/en-US/jobs/12345"

    base_host = urlparse(cxs_url).netloc
    url = ext_path if ext_path.startswith("http") else f"https://{base_host}{ext_path}"

    assert url == "https://acme.wd5.myworkdayjobs.com/en-US/jobs/12345"
    assert url.count("https://") == 1


def test_cxs_empty_page():
    parser = WorkdayParser()
    data = {"jobPostings": [], "total": 0}
    cxs_url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/acme/jobs"
    jobs, done = parser._parse_cxs_page(data, cxs_url, 0)
    assert len(jobs) == 0
    assert done is True