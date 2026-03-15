"""Instant quote range calculation for quotable services."""


def calculate_quote_range(
    service: dict,
    details: dict | None = None,
) -> dict | None:
    """Calculate an instant price quote range for a quotable service.

    Parameters
    ----------
    service : dict
        A service definition with keys: ``name``, ``duration_min``,
        ``price_min``, ``price_max``, ``quotable``.
    details : dict | None
        Optional additional detail about the project (reserved for future
        complexity-based adjustments).

    Returns
    -------
    dict | None
        ``{"min": float, "max": float, "service_name": str}`` if the service
        is quotable and has pricing data, otherwise ``None``.
    """
    if not service.get("quotable"):
        return None

    price_min = service.get("price_min")
    price_max = service.get("price_max")

    if price_min is None and price_max is None:
        return None

    # Ensure we have both bounds
    if price_min is None:
        price_min = price_max
    if price_max is None:
        price_max = price_min

    price_min = float(price_min)
    price_max = float(price_max)

    # Apply optional detail-based adjustments
    if details:
        # Complexity multiplier: "low" 0.8, "medium" 1.0, "high" 1.3
        complexity = details.get("complexity", "medium")
        multipliers = {"low": 0.8, "medium": 1.0, "high": 1.3}
        mult = multipliers.get(complexity, 1.0)
        price_min = round(price_min * mult, 2)
        price_max = round(price_max * mult, 2)

        # Square footage adjustment for area-based services
        sqft = details.get("square_footage")
        if sqft and isinstance(sqft, (int, float)):
            base_sqft = details.get("base_square_footage", 1000)
            if base_sqft > 0:
                factor = sqft / base_sqft
                price_min = round(price_min * factor, 2)
                price_max = round(price_max * factor, 2)

    return {
        "min": price_min,
        "max": price_max,
        "service_name": service.get("name", "Service"),
    }
