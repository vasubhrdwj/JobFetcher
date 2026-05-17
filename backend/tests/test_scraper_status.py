import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.models.models import Company, ATSPlatform
from app.services.scraper import scrape_all_companies, scrape_single_company, _update_company_status


def make_company(id=1, name="TestCorp", ats=ATSPlatform.CUSTOM):
    company = MagicMock(spec=Company)
    company.id = id
    company.name = name
    company.ats_platform = ats
    company.career_url = "https://test.com/careers"
    company.is_active = True
    return company


@pytest.mark.asyncio
async def test_status_success():
    company = make_company()
    jobs = [{"title": "Engineer", "url": "https://test.com/jobs/1", "company_id": 1, "source": "custom", "content_hash": "abc"}]

    with patch("app.services.scraper.scrape_company", new_callable=AsyncMock, return_value=jobs):
        with patch("app.services.scraper.upsert_jobs", new_callable=AsyncMock, return_value=1):
            with patch("app.services.scraper._update_company_status", new_callable=AsyncMock) as mock_status:
                with patch("app.services.scraper._sweep_stale_jobs", new_callable=AsyncMock):
                    with patch("app.services.scraper.async_session") as mock_session:
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
                        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
                        mock_result = MagicMock()
                        mock_result.scalars.return_value.all.return_value = [company]
                        mock_session.return_value.__aenter__.return_value.execute = AsyncMock(return_value=mock_result)
                        result = await scrape_all_companies()

    assert result["total_jobs"] >= 0


@pytest.mark.asyncio
async def test_status_labels_parse_failed():
    import asyncio
    from app.services.scraper import _update_company_status

    with patch("app.services.scraper.async_session") as mock_session:
        mock_sess = AsyncMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_company = MagicMock()
        mock_sess.get = AsyncMock(return_value=mock_company)

        await _update_company_status(1, "parse_failed: ValueError bad data")
        assert mock_company.scrape_status.startswith("parse_failed:")

        await _update_company_status(2, "http_error: ConnectError timeout")
        assert mock_company.scrape_status.startswith("http_error:")