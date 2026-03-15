"""Tests for the instant quote range calculation service."""

from app.services.quote import calculate_quote_range


def test_quotable_service():
    """A quotable service with pricing should return a valid range."""
    service = {
        "name": "Roof Repair",
        "duration_min": 120,
        "price_min": 300,
        "price_max": 2500,
        "quotable": True,
    }
    result = calculate_quote_range(service)
    assert result is not None
    assert result["min"] == 300
    assert result["max"] == 2500
    assert result["service_name"] == "Roof Repair"


def test_non_quotable_service():
    """A non-quotable service should return None."""
    service = {
        "name": "Inspection",
        "duration_min": 60,
        "quotable": False,
    }
    result = calculate_quote_range(service)
    assert result is None


def test_quotable_without_prices():
    """A quotable service missing both price bounds should return None."""
    service = {
        "name": "Custom Work",
        "duration_min": 120,
        "quotable": True,
    }
    result = calculate_quote_range(service)
    assert result is None


def test_quotable_with_only_min():
    """When only price_min is given, price_max should default to price_min."""
    service = {
        "name": "Gutter Cleaning",
        "duration_min": 60,
        "price_min": 100,
        "price_max": None,
        "quotable": True,
    }
    result = calculate_quote_range(service)
    assert result is not None
    assert result["min"] == 100.0
    assert result["max"] == 100.0


def test_quotable_with_only_max():
    """When only price_max is given, price_min should default to price_max."""
    service = {
        "name": "Leak Fix",
        "duration_min": 60,
        "price_min": None,
        "price_max": 500,
        "quotable": True,
    }
    result = calculate_quote_range(service)
    assert result is not None
    assert result["min"] == 500.0
    assert result["max"] == 500.0


def test_complexity_multiplier_high():
    """The 'high' complexity multiplier should increase the price range."""
    service = {
        "name": "Roof Replacement",
        "duration_min": 180,
        "price_min": 1000,
        "price_max": 5000,
        "quotable": True,
    }
    details = {"complexity": "high"}
    result = calculate_quote_range(service, details=details)
    assert result is not None
    assert result["min"] == 1300.0
    assert result["max"] == 6500.0


def test_complexity_multiplier_low():
    """The 'low' complexity multiplier should decrease the price range."""
    service = {
        "name": "Roof Repair",
        "duration_min": 120,
        "price_min": 1000,
        "price_max": 2000,
        "quotable": True,
    }
    details = {"complexity": "low"}
    result = calculate_quote_range(service, details=details)
    assert result is not None
    assert result["min"] == 800.0
    assert result["max"] == 1600.0


def test_square_footage_adjustment():
    """Square footage factor should scale prices proportionally."""
    service = {
        "name": "Roof Replacement",
        "duration_min": 180,
        "price_min": 1000,
        "price_max": 5000,
        "quotable": True,
    }
    details = {"square_footage": 2000, "base_square_footage": 1000}
    result = calculate_quote_range(service, details=details)
    assert result is not None
    assert result["min"] == 2000.0
    assert result["max"] == 10000.0


def test_missing_quotable_key():
    """A service dict without the 'quotable' key should return None."""
    service = {"name": "Mystery Service", "duration_min": 60}
    result = calculate_quote_range(service)
    assert result is None
