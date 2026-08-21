"""Synthetic unit counts for demo parcel layers.

Public parcel datasets often ship without a unit count, but the whole point of
the two-tool architecture is that the ordinance section depends on how many
units the building has. Without that field there is nothing for the parcel tool
to contribute, and the 30-unit vs single-family demo cannot be shown.

This module fabricates a unit count so the demo works. It is **not real data**.
The frontend normally fills UNITS in at upload time; this is the fallback for
requests that arrive without it. Delete both once the layer carries real counts.

The count is derived from a hash of the APN rather than randomly generated, so
the same parcel always reports the same number. A random value would change on
every click and the "same question, different parcel, different answer" test
would not be reproducible.
"""
import hashlib

# Buckets sized so a demo lands on both sides of the ordinance's 10-unit
# threshold often enough to show the difference. Weights are out of 100.
_BUCKETS = (
    (40, 1, 1),      # single-family — Section 9.68.050, one month's rent
    (25, 2, 9),      # small multi-family — still under the threshold
    (35, 10, 60),    # 10+ units — Section 9.68.060, the dollar table
)


def _stable_int(apn: str) -> int:
    """A repeatable pseudo-random integer for one APN.

    md5 rather than hash() because Python randomises str hashing per process,
    which would give a parcel a different unit count after every restart.
    """
    digest = hashlib.md5(apn.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def demo_unit_count(apn: str) -> int:
    """Fabricate a stable unit count for the given APN."""
    seed = _stable_int(apn)
    pick = seed % 100

    cursor = 0
    for weight, low, high in _BUCKETS:
        cursor += weight
        if pick < cursor:
            if low == high:
                return low
            # A second slice of the same hash, so the bucket choice and the
            # value inside it are not correlated.
            return low + (seed // 100) % (high - low + 1)

    return 1  # unreachable while the weights sum to 100


def apply_demo_units(apn: str, attributes: dict) -> dict:
    """Fill in UNITS when the request arrived without unit data.

    Only ever fills a gap — attributes that really do carry UNITS are left alone.
    """
    if not apn or not attributes:
        return attributes

    if attributes.get("UNITS") not in (None, "", "null", 0, "0"):
        return attributes

    attributes["UNITS"] = demo_unit_count(apn)
    return attributes
