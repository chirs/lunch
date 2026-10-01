#!/usr/bin/env python3
"""Refresh www/places.json: discover places, time the drive, score them.

    ./update.py                 # everything; needs GOOGLE_MAPS_API_KEY in .env
    ./update.py --skip-google   # drive times and scores only, uses no quota

Google's Nearby Search returns at most 20 places per call with no paging, so
discovery walks a hex grid of circles around the office and splits any circle
that comes back full. Hand-written fields (notes, my_rating, hidden) survive
every run.
"""

import argparse
import datetime
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACES = ROOT / "www/places.json"
ENV = ROOT / ".env"
USER_AGENT = "lunch.edgemon.org (github.com/chirs/lunch)"

SEARCH_MILES = 8
CELL_METERS = 1500
MIN_CELL_METERS = 375  # two splits: 1500 -> 750 -> 375
MAX_CALLS = 800  # 1,000 a month are free
PAGE_SIZE = 20
MAX_MINUTES = 15
MIN_REVIEWS = 20
HAND_FIELDS = ("notes", "my_rating", "hidden")

FIELD_MASK = ",".join(
    f"places.{field}"
    for field in (
        "id",
        "displayName",
        "location",
        "formattedAddress",
        "primaryType",
        "businessStatus",
        "rating",
        "userRatingCount",
        "priceLevel",
        "regularOpeningHours.periods",
        "websiteUri",
        "googleMapsUri",
    )
)
PRICES = {
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}
# National fast food and delivery pizza. Matched against the start of the name.
CHAINS = (
    "arbys",
    "burger king",
    "churchs",
    "dairy queen",
    "dominos",
    "jack in the box",
    "kfc",
    "little caesars",
    "long john silvers",
    "marcos pizza",
    "mcdonalds",
    "papa johns",
    "pizza hut",
    "pizza patron",
    "popeyes",
    "sonic drive-in",
    "subway",
    "taco bell",
    "taco bueno",
    "wendys",
)
GENERIC_TYPES = {None, "restaurant", "fast_food_restaurant", "meal_takeaway", "meal_delivery", "food_court"}
CUISINES = {
    "hamburger_restaurant": "Burgers",
    "pizza_restaurant": "Pizza",
    "sandwich_shop": "Sandwiches",
    "steak_house": "Steakhouse",
    "sushi_restaurant": "Japanese",
    "ramen_restaurant": "Japanese",
}


def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def offset(lat, lon, east_m, north_m):
    return (
        lat + north_m / 111_320,
        lon + east_m / (111_320 * math.cos(math.radians(lat))),
    )


def hex_grid(lat, lon, radius_m, cell_m):
    """Centers of circles of radius cell_m that together cover the disc."""
    dx, dy = cell_m * math.sqrt(3), cell_m * 1.5
    rows = math.ceil(radius_m / dy) + 1
    cols = math.ceil(radius_m / dx) + 1
    centers = []
    for row in range(-rows, rows + 1):
        for col in range(-cols, cols + 1):
            east, north = (col + (row % 2) / 2) * dx, row * dy
            if math.hypot(east, north) <= radius_m + cell_m:
                centers.append(offset(lat, lon, east, north))
    return centers


def split(lat, lon, radius_m):
    """Seven circles of half the radius that cover the original."""
    ring = radius_m * math.sqrt(3) / 2
    centers = [(lat, lon)]
    for k in range(6):
        angle = math.radians(60 * k)
        centers.append(offset(lat, lon, ring * math.cos(angle), ring * math.sin(angle)))
    return [(c_lat, c_lon, radius_m / 2) for c_lat, c_lon in centers]


def search_nearby(key, lat, lon, radius_m):
    body = {
        "includedTypes": ["restaurant"],
        "maxResultCount": PAGE_SIZE,
        "rankPreference": "POPULARITY",
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius_m}
        },
    }
    request = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchNearby",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("places", [])


def discover(office, search):
    """Every place the search finds within SEARCH_MILES, keyed by Google id."""
    cells = deque(
        (lat, lon, CELL_METERS)
        for lat, lon in hex_grid(office["lat"], office["lon"], SEARCH_MILES * 1609.34, CELL_METERS)
    )
    found, calls, truncated = {}, 0, 0
    while cells and calls < MAX_CALLS:
        lat, lon, radius = cells.popleft()
        results = search(lat, lon, radius)
        calls += 1
        for place in results:
            found[place["id"]] = place
        if len(results) == PAGE_SIZE:
            if radius / 2 >= MIN_CELL_METERS:
                cells.extend(split(lat, lon, radius))
            else:
                truncated += 1
        if calls % 25 == 0:
            print(f"  {calls} calls, {len(found)} places, {len(cells)} cells queued")
    print(f"{calls} calls, {len(found)} places found")
    if cells:
        print(f"stopped at {MAX_CALLS} calls with {len(cells)} cells unsearched")
    if truncated:
        print(f"{truncated} smallest cells were still full, so some places there are missing")
    return found


def open_for_lunch(place):
    """Open at noon on some weekday. Places with no hours listed pass."""
    periods = place.get("regularOpeningHours", {}).get("periods")
    if not periods:
        return True
    week = 7 * 1440
    for period in periods:
        if "close" not in period:  # always open
            return True
        start, end = (
            point["day"] * 1440 + point["hour"] * 60 + point["minute"]
            for point in (period["open"], period["close"])
        )
        if end <= start:
            end += week
        for day in range(1, 6):  # Google's day 0 is Sunday
            noon = day * 1440 + 720
            if start <= noon < end or start <= noon + week < end:
                return True
    return False


def is_chain(name):
    plain = re.sub(r"[^a-z0-9 -]", "", name.lower().replace("é", "e").replace("ó", "o"))
    return plain.startswith(CHAINS)


def drop_reason(place, office):
    if place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
        return "closed"
    location = place["location"]
    miles = haversine_miles(office["lat"], office["lon"], location["latitude"], location["longitude"])
    if miles > SEARCH_MILES:
        return "outside the search area"
    if place.get("userRatingCount", 0) < MIN_REVIEWS:
        return f"under {MIN_REVIEWS} reviews"
    if is_chain(place["displayName"]["text"]):
        return "fast-food chain"
    if not open_for_lunch(place):
        return "not open for weekday lunch"
    return None


def cuisine(primary_type):
    if primary_type in GENERIC_TYPES:
        return "Other"
    if primary_type in CUISINES:
        return CUISINES[primary_type]
    return primary_type.removesuffix("_restaurant").replace("_", " ").title()


def to_record(place):
    record = {
        "id": place["id"],
        "name": place["displayName"]["text"],
        "cuisine": cuisine(place.get("primaryType")),
        "address": place["formattedAddress"].removesuffix(", USA"),
        "lat": round(place["location"]["latitude"], 6),
        "lon": round(place["location"]["longitude"], 6),
        "rating": place["rating"],
        "reviews": place["userRatingCount"],
        "maps": place["googleMapsUri"],
    }
    if place.get("priceLevel") in PRICES:
        record["price"] = PRICES[place["priceLevel"]]
    if "websiteUri" in place:
        record["url"] = place["websiteUri"]
    return record


def merge(existing, records):
    """Fresh records, keeping minutes and hand fields from the entries they replace.

    Also returns the existing entries with hand fields that found no match, so
    nothing hand-written disappears silently.
    """
    old = {place["id"]: place for place in existing if "id" in place}
    for record in records:
        previous = old.get(record["id"], {})
        for field in ("minutes", *HAND_FIELDS):
            if field in previous:
                record[field] = previous[field]
    kept = {record["id"] for record in records}
    lost = [
        place
        for place in existing
        if place.get("id") not in kept and any(place.get(field) for field in HAND_FIELDS)
    ]
    return records, lost


def drive_minutes(office, places):
    """Free-flow driving minutes from the office, or None where OSRM finds no route."""
    minutes = []
    for start in range(0, len(places), 100):
        if start:
            time.sleep(1)
        batch = places[start : start + 100]
        coords = ";".join(f"{p['lon']},{p['lat']}" for p in [office, *batch])
        request = urllib.request.Request(
            f"https://router.project-osrm.org/table/v1/driving/{coords}?sources=0",
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            seconds = json.load(response)["durations"][0][1:]
        minutes += [None if s is None else round(s / 60, 1) for s in seconds]
    return minutes


def add_scores(places):
    """Google's rating pulled toward the average, harder the fewer the reviews."""
    rated = [p for p in places if "rating" in p]
    if rated:
        average = statistics.mean(p["rating"] for p in rated)
        weight = statistics.median(p["reviews"] for p in rated)
    for place in places:
        if place.get("my_rating"):
            place["score"] = place["my_rating"]
        elif "rating" in place:
            n = place["reviews"]
            place["score"] = round((n * place["rating"] + weight * average) / (n + weight), 2)
        else:
            place.pop("score", None)


def api_key():
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key and ENV.exists():
        for line in ENV.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GOOGLE_MAPS_API_KEY":
                key = value.strip().strip("\"'")
    if not key:
        sys.exit("set GOOGLE_MAPS_API_KEY in .env, or pass --skip-google")
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-google", action="store_true", help="drive times and scores only")
    args = parser.parse_args()

    data = json.loads(PLACES.read_text())
    office = data["office"]

    if not args.skip_google:
        key = api_key()
        found = discover(office, lambda lat, lon, radius: search_nearby(key, lat, lon, radius))
        reasons = Counter()
        records = []
        for place in found.values():
            reason = drop_reason(place, office)
            if reason:
                reasons[reason] += 1
            else:
                records.append(to_record(place))
        for reason, count in reasons.most_common():
            print(f"  dropped {count}: {reason}")
        data["places"], lost = merge(data["places"], records)
        for place in lost:
            print(f"  hand-written entry no longer matched: {place['name']}")
        data["updated"] = datetime.datetime.now().astimezone().date().isoformat()

    untimed = [p for p in data["places"] if "minutes" not in p]
    for place, minutes in zip(untimed, drive_minutes(office, untimed)):
        place["minutes"] = minutes
    in_range = [p for p in data["places"] if p["minutes"] is not None and p["minutes"] <= MAX_MINUTES]
    print(f"timed {len(untimed)} places; dropped {len(data['places']) - len(in_range)} over {MAX_MINUTES} minutes")

    add_scores(in_range)
    data["places"] = sorted(in_range, key=lambda p: (p["name"].lower(), p["address"]))
    PLACES.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(in_range)} places written")


if __name__ == "__main__":
    main()
