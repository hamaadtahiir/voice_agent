"""Tests for the rule-based lead scoring service."""

from app.services.lead_scoring import score_lead


def test_score_lead_full_info():
    """A lead with all qualification signals should score above 80."""
    data = {
        "name": "John Doe",
        "phone": "+15551234567",
        "email": "john@example.com",
        "in_service_area": True,
        "pain_point": "My roof is leaking badly after the storm",
        "identified_service": "Roof Repair",
        "media_urls": ["https://example.com/photo1.jpg"],
        "responded_in_business_hours": True,
    }
    score, breakdown = score_lead(data)
    assert score > 80, f"Expected score > 80 but got {score}"
    assert breakdown["has_name"] == 15
    assert breakdown["has_phone"] == 20
    assert breakdown["has_email"] == 10
    assert breakdown["in_service_area"] == 20
    assert breakdown["has_pain_point"] == 15
    assert breakdown["service_identified"] == 10
    assert breakdown["has_media"] == 5
    assert breakdown["business_hours"] == 5


def test_score_lead_minimal_info():
    """A lead with no data at all should score zero."""
    data = {}
    score, breakdown = score_lead(data)
    assert score == 0
    assert all(v == 0 for v in breakdown.values())


def test_score_lead_out_of_area():
    """A lead with contact info but outside service area should score below 50."""
    data = {
        "name": "Jane",
        "phone": "+15559999999",
        "in_service_area": False,
    }
    score, breakdown = score_lead(data)
    assert score < 50, f"Expected score < 50 but got {score}"
    assert breakdown.get("in_service_area", 0) == 0


def test_score_lead_only_name():
    """A lead with only a name should get exactly 15 points."""
    data = {"name": "Alice"}
    score, breakdown = score_lead(data)
    assert score == 15
    assert breakdown["has_name"] == 15


def test_score_lead_phone_and_email():
    """Phone + email together should total 30 points."""
    data = {"phone": "+15551234567", "email": "test@example.com"}
    score, breakdown = score_lead(data)
    assert score == 30
    assert breakdown["has_phone"] == 20
    assert breakdown["has_email"] == 10


def test_score_lead_capped_at_100():
    """The score should never exceed 100 even with maximum data."""
    data = {
        "name": "John Doe",
        "phone": "+15551234567",
        "email": "john@example.com",
        "in_service_area": True,
        "pain_point": "Urgent leak",
        "identified_service": "Emergency Repair",
        "media_urls": ["https://example.com/photo.jpg"],
        "responded_in_business_hours": True,
    }
    score, _ = score_lead(data)
    assert score <= 100


def test_score_lead_empty_media_list():
    """An empty media_urls list should not award media points."""
    data = {"name": "Bob", "media_urls": []}
    score, breakdown = score_lead(data)
    assert breakdown["has_media"] == 0
    assert score == 15
