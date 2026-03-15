"""Rule-based lead scoring (0-100)."""


def score_lead(lead_data: dict) -> tuple[int, dict]:
    """Score a lead on a 0-100 scale.

    Parameters
    ----------
    lead_data : dict
        Keys may include: name, phone, email, location_zip, location_city,
        in_service_area, pain_point, identified_service, media_urls,
        responded_in_business_hours.

    Returns
    -------
    tuple[int, dict]
        The total score and a breakdown dict mapping each criterion to its
        points awarded.

    Scoring rules
    -------------
    - Has name:                       +15
    - Has phone:                      +20
    - Has email:                      +10
    - In service area:                +20
    - Has pain point described:       +15
    - Service identified:             +10
    - Has media / photos:             +5
    - Responded within business hours: +5
    """
    score = 0
    breakdown: dict[str, int] = {}

    # Name
    if lead_data.get("name"):
        breakdown["has_name"] = 15
        score += 15
    else:
        breakdown["has_name"] = 0

    # Phone
    if lead_data.get("phone"):
        breakdown["has_phone"] = 20
        score += 20
    else:
        breakdown["has_phone"] = 0

    # Email
    if lead_data.get("email"):
        breakdown["has_email"] = 10
        score += 10
    else:
        breakdown["has_email"] = 0

    # Service area
    if lead_data.get("in_service_area"):
        breakdown["in_service_area"] = 20
        score += 20
    else:
        breakdown["in_service_area"] = 0

    # Pain point
    if lead_data.get("pain_point"):
        breakdown["has_pain_point"] = 15
        score += 15
    else:
        breakdown["has_pain_point"] = 0

    # Identified service
    if lead_data.get("identified_service"):
        breakdown["service_identified"] = 10
        score += 10
    else:
        breakdown["service_identified"] = 0

    # Media / photos
    media = lead_data.get("media_urls")
    if media and len(media) > 0:
        breakdown["has_media"] = 5
        score += 5
    else:
        breakdown["has_media"] = 0

    # Responded within business hours
    if lead_data.get("responded_in_business_hours"):
        breakdown["business_hours"] = 5
        score += 5
    else:
        breakdown["business_hours"] = 0

    return min(score, 100), breakdown
