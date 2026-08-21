"""Parcel attribute tool.

Attributes arrive with each request (the frontend already has them from the
clicked feature), so nothing is stored between requests — that keeps two users
from ever seeing each other's parcel.
"""
from app.parcel_data.demo_units import apply_demo_units

# Fields worth showing the LLM. Anything else is either noise or too large.
USEFUL_FIELDS = (
    "APN",
    "UNITS",
    "ZONEGIS",
    "LANDUSEGIS",
    "YEARBUILT",
    "STORIES",
    "BUILDINGSQ",
    "LOTSQFT",
    "HRBCATEGOR",
    "FLOODZONE",
    "ZIP",
    "JURISDICTI",
)

# Geometry is thousands of characters of coordinates — useless to the model and
# expensive in tokens. The map needs it; the agent does not.
EXCLUDED_FIELDS = ("Geometry", "GeometryJsonb", "geometry", "SHAPE")


def get_parcel_attributes(apn: str | None, raw: dict | None) -> dict | None:
    """Clean the attributes the frontend sent for the selected parcel.

    Returns None when there is nothing usable, so the agent can say "no parcel
    data available" instead of guessing.
    """
    if not apn or not raw:
        return None

    cleaned = {}

    # Prefer the documented fields, in a stable order.
    for field in USEFUL_FIELDS:
        value = raw.get(field)
        if value not in (None, "", "null"):
            cleaned[field] = value

    # Fall back to whatever else came through, for cities using different column
    # names — minus geometry and anything oversized.
    if len(cleaned) <= 1:
        for key, value in raw.items():
            if key in EXCLUDED_FIELDS or value in (None, "", "null"):
                continue
            if isinstance(value, str) and len(value) > 200:
                continue
            cleaned[key] = value

    if not cleaned:
        return None

    cleaned.setdefault("APN", apn)

    # Demo layers may carry no unit count. Fabricated, and only when absent.
    return apply_demo_units(apn, cleaned)
