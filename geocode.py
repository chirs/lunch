#!/usr/bin/env python3
"""Fill in missing lat/lon in www/places.json from each place's address.

Add a place with a name and address, run this, commit. Lookups go to Nominatim
(OpenStreetMap), which allows one request a second and requires a User-Agent.
"""

import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PLACES = Path(__file__).resolve().parent / "www/places.json"
USER_AGENT = "lunch.edgemon.org geocoder (github.com/chirs/lunch)"


def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def street_address(address):
    """Drop the suite number, which Nominatim fails to match on."""
    return re.sub(r"\s+(#|Ste\.?\s|Suite\s|Unit\s)\s*\w+", "", address)


def geocode(address):
    query = urllib.parse.urlencode(
        {"q": street_address(address), "format": "json", "limit": 1, "countrycodes": "us"}
    )
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        results = json.load(response)
    if not results:
        return None
    return round(float(results[0]["lat"]), 6), round(float(results[0]["lon"]), 6)


def main():
    data = json.loads(PLACES.read_text())
    office = data["office"]
    missing = [p for p in data["places"] if "lat" not in p or "lon" not in p]
    failed = []
    for i, place in enumerate(missing):
        if i:
            time.sleep(1)
        found = geocode(place["address"])
        if found is None:
            failed.append(place["name"])
            continue
        place["lat"], place["lon"] = found
        miles = haversine_miles(office["lat"], office["lon"], *found)
        print(f"{place['name']}: {found[0]}, {found[1]} ({miles:.1f} mi from the office)")
    PLACES.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if failed:
        sys.exit("no match for: " + ", ".join(failed))


if __name__ == "__main__":
    main()
