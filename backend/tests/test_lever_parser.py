import pytest
from datetime import datetime, timezone
from app.services.ats_parser import LeverParser


def test_created_at_millis_to_iso():
    parser = LeverParser()

    millis = 1715000000000
    expected_iso = datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat()

    posting = {
        "text": "Software Engineer",
        "url": "https://jobs.lever.co/test/abc123",
        "createdAt": millis,
        "categories": {"location": "Remote", "department": "Engineering", "commitment": "Full-time"},
        "description": {"plain": "Test description"},
    }

    result = parser._parse_api_jobs([posting])
    assert len(result) == 1
    assert result[0]["posted_at"] == expected_iso
    assert result[0]["title"] == "Software Engineer"
    assert result[0]["source"] == "lever_api"


def test_created_at_string_passthrough():
    parser = LeverParser()

    posting = {
        "text": "Product Manager",
        "url": "https://jobs.lever.co/test/def456",
        "createdAt": "2024-05-01T12:00:00Z",
        "categories": {"location": "NYC"},
        "description": {},
    }

    result = parser._parse_api_jobs([posting])
    assert len(result) == 1
    assert result[0]["posted_at"] == "2024-05-01T12:00:00Z"