#!/usr/bin/env python3
"""Refresh www/places.json: discover places, time the drive, score them.

    ./update.py            # everything; needs GOOGLE_MAPS_API_KEY in .env
    ./update.py --cached   # no Google calls: re-filter the last results saved
                           # in google_raw.json, then drive times and scores

Google's Nearby Search returns at most 20 places per call with no paging, so
discovery walks a hex grid of circles around the office and splits any circle
that comes back full. Hand-written fields (notes, my_rating, visited, hidden)
survive every run.
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
RAW = ROOT / "google_raw.json"
ENV = ROOT / ".env"
USER_AGENT = "lunch.edgemon.org (github.com/chirs/lunch)"

SEARCH_MILES = 12  # about as far as MAX_MINUTES reaches along the freeways
CELL_METERS = 1500
MIN_CELL_METERS = 375  # two splits: 1500 -> 750 -> 375
MAX_CALLS = 800  # 1,000 a month are free
# Icehouses and sports bars often lack Google's "restaurant" type, so they get
# a second pass that asks whether each serves lunch. That extra field bills as
# a different SKU with its own 1,000 free calls.
BAR_TYPES = ["bar", "bar_and_grill", "sports_bar", "pub", "brewpub"]
MAX_BAR_CALLS = 200
PAGE_SIZE = 20
MAX_MINUTES = 20
MIN_REVIEWS = 20
HAND_FIELDS = ("notes", "my_rating", "visited", "hidden")

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
# Primary types that count as somewhere to eat lunch, besides anything ending
# in _restaurant. Google also tags gas stations, smoothie shops and strip clubs
# as restaurants; their primary types are not here.
LUNCH_TYPES = {
    "restaurant",
    "meal_takeaway",
    "food_court",
    "sandwich_shop",
    "deli",
    "bagel_shop",
    "salad_shop",
    "steak_house",
    "diner",
    "cafe",
    "bistro",
    "kebab_shop",
    "noodle_shop",
    *BAR_TYPES,
}
# Anything not listed becomes its type name: korean_restaurant -> Korean.
CUISINES = {
    "restaurant": "Other",
    "meal_takeaway": "Other",
    "food_court": "Other",
    "fine_dining_restaurant": "Other",
    "fast_food_restaurant": "Fast Food",
    "family_restaurant": "American",
    "southwestern_us_restaurant": "American",
    "hamburger_restaurant": "Burgers",
    "pizza_restaurant": "Pizza",
    "sandwich_shop": "Sandwiches",
    "deli": "Sandwiches",
    "bagel_shop": "Sandwiches",
    "salad_shop": "Salads",
    "steak_house": "Steakhouse",
    "sushi_restaurant": "Japanese",
    "ramen_restaurant": "Japanese",
    "taco_restaurant": "Mexican",
    "tex_mex_restaurant": "Mexican",
    "korean_barbecue_restaurant": "Korean",
    "chicken_wings_restaurant": "Chicken",
    "south_indian_restaurant": "Indian",
    "hot_pot_restaurant": "Chinese",
    "dim_sum_restaurant": "Chinese",
    "noodle_shop": "Asian",
    "asian_fusion_restaurant": "Asian",
    "gyro_restaurant": "Greek",
    "shawarma_restaurant": "Middle Eastern",
    "kebab_shop": "Middle Eastern",
    "breakfast_restaurant": "Breakfast",
    "brunch_restaurant": "Breakfast",
    "yakiniku_restaurant": "Japanese",
    **dict.fromkeys(BAR_TYPES, "Bar & Grill"),
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


def search_nearby(key, lat, lon, radius_m, types, field_mask=FIELD_MASK):
    body = {
        "includedTypes": types,
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
            "X-Goog-FieldMask": field_mask,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("places", [])


def discover(office, search, max_calls):
    """Every place the search finds within SEARCH_MILES, keyed by Google id.

    Cells are searched breadth-first, so when max_calls runs out the whole area
    has been covered coarsely and only the densest spots are short.
    """
    cells = deque(
        (lat, lon, CELL_METERS)
        for lat, lon in hex_grid(office["lat"], office["lon"], SEARCH_MILES * 1609.34, CELL_METERS)
    )
    found, calls, truncated = {}, 0, 0
    while cells and calls < max_calls:
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
            print(f"  {calls} calls, {len(found)} places, {len(cells)} cells queued", flush=True)
    print(f"{calls} calls, {len(found)} places found")
    if cells:
        print(f"stopped at {max_calls} calls with {len(cells)} cells unsearched")
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


def week_hours(place):
    """Opening hours as seven strings, Sunday first, or None if Google lists none.

    A day reads "1100-2200", "1100-1400,1700-2200", or "" when closed. A range
    that runs past midnight stays on the day it opens ("1700-0200"), and a
    place that never closes is "0000-2400" every day.
    """
    periods = place.get("regularOpeningHours", {}).get("periods")
    if not periods:
        return None
    if any("close" not in period for period in periods):
        return ["0000-2400"] * 7
    days = [[] for _ in range(7)]
    for period in periods:
        start, end = period["open"], period["close"]
        days[start["day"]].append(
            f"{start['hour']:02d}{start['minute']:02d}-{end['hour']:02d}{end['minute']:02d}"
        )
    return [",".join(sorted(day)) for day in days]


def is_chain(name):
    plain = re.sub(r"[^a-z0-9 -]", "", name.lower().replace("é", "e").replace("ó", "o"))
    return plain.startswith(CHAINS)


def drop_reason(place, office):
    if place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
        return "closed"
    primary_type = place.get("primaryType") or ""
    if not primary_type.endswith("_restaurant") and primary_type not in LUNCH_TYPES:
        return "not a restaurant"
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


# The site's first cuisine dropdown; the second drills into one group. A
# cuisine listed nowhere lands in "Other", and a run names any such stragglers.
GROUPS = {
    "Mexican & Latin": [
        "Mexican",
        "Latin American",
        "Cuban",
        "Brazilian",
        "Colombian",
        "Argentinian",
        "Peruvian",
        "Caribbean",
    ],
    "American": ["American", "Barbecue", "Steakhouse", "Breakfast", "Diner", "Cajun", "Soul Food", "Hawaiian"],
    "Burgers & Sandwiches": ["Burgers", "Chicken", "Sandwiches", "Fast Food", "Cafe", "Salads"],
    "Bar & Grill": ["Bar & Grill"],
    "Asian": ["Japanese", "Korean", "Chinese", "Thai", "Vietnamese", "Asian", "Indonesian", "Filipino"],
    "South Asian": ["Indian", "Pakistani", "Bangladeshi", "Sri Lankan"],
    "Italian & European": ["Pizza", "Italian", "French", "Irish", "German", "Spanish", "Tapas", "European", "Bistro"],
    "Mediterranean": ["Mediterranean", "Middle Eastern", "Greek", "Halal", "Persian", "Turkish"],
    "Seafood": ["Seafood"],
    "African": ["African", "Ethiopian"],
    "Other": ["Other", "Buffet", "Vegetarian", "Dessert"],
}
CUISINE_GROUPS = {cuisine: group for group, cuisines in GROUPS.items() for cuisine in cuisines}


def cuisine(primary_type):
    if primary_type in CUISINES:
        return CUISINES[primary_type]
    return primary_type.removesuffix("_restaurant").replace("_", " ").title()


def to_record(place):
    record = {
        "id": place["id"],
        "name": place["displayName"]["text"],
        "cuisine": cuisine(place["primaryType"]),
        "address": place["formattedAddress"].removesuffix(", USA"),
        "lat": round(place["location"]["latitude"], 6),
        "lon": round(place["location"]["longitude"], 6),
        "rating": place["rating"],
        "reviews": place["userRatingCount"],
        "maps": place["googleMapsUri"].split("&g_mp=")[0],  # the rest is tracking
    }
    if place.get("priceLevel") in PRICES:
        record["price"] = PRICES[place["priceLevel"]]
    if "websiteUri" in place:
        record["url"] = place["websiteUri"]
    hours = week_hours(place)
    if hours:
        record["hours"] = hours
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


def nearest_per_name(places):
    """One pin per chain: the closest branch, plus any branch with hand fields."""
    nearest = {}
    for place in places:
        best = nearest.get(place["name"])
        if best is None or place["minutes"] < best["minutes"]:
            nearest[place["name"]] = place
    return [
        place
        for place in places
        if nearest[place["name"]] is place or any(place.get(field) for field in HAND_FIELDS)
    ]


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


def tier_cuts(places):
    """Score cuts, in tenths, that put about a fifth of the places in each outer tier."""
    scores = [round(p["score"], 1) for p in places if "score" in p]
    steps = sorted(set(scores))

    def off_a_fifth(count):
        return abs(count / len(scores) - 0.2)

    low = min(steps, key=lambda cut: off_a_fifth(sum(s < cut for s in scores)))
    high = min(steps, key=lambda cut: off_a_fifth(sum(s >= cut for s in scores)))
    return [low, high]


def write_places(path, data):
    """One place per line: half the size of indented JSON, and diffs stay per place."""
    head = json.dumps({k: v for k, v in data.items() if k != "places"}, ensure_ascii=False, indent=2)
    places = ",\n".join(
        json.dumps(place, ensure_ascii=False, separators=(",", ":")) for place in data["places"]
    )
    path.write_text(f'{head[:-2]},\n  "places": [\n{places}\n  ]\n}}\n')


def api_key():
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key and ENV.exists():
        for line in ENV.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GOOGLE_MAPS_API_KEY":
                key = value.strip().strip("\"'")
    if not key:
        sys.exit("set GOOGLE_MAPS_API_KEY in .env, or pass --cached")
    return key


def fetch(office):
    key = api_key()
    print("restaurants:")
    found = discover(
        office, lambda *cell: search_nearby(key, *cell, ["restaurant"]), MAX_CALLS
    )
    print("bars that serve lunch:")
    bars = discover(
        office,
        lambda *cell: search_nearby(key, *cell, BAR_TYPES, FIELD_MASK + ",places.servesLunch"),
        MAX_BAR_CALLS,
    )
    found.update({id: bar for id, bar in bars.items() if bar.get("servesLunch")})
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cached", action="store_true", help="reuse google_raw.json, no API calls")
    args = parser.parse_args()

    data = json.loads(PLACES.read_text())
    office = data["office"]

    if not args.cached:
        today = datetime.datetime.now().astimezone().date().isoformat()
        RAW.write_text(json.dumps({"fetched": today, "places": fetch(office)}))
    if RAW.exists():
        raw = json.loads(RAW.read_text())
        reasons = Counter()
        records = []
        for place in raw["places"].values():
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
        data["updated"] = raw["fetched"]
    else:
        print("no google_raw.json; keeping the current list")

    untimed = [p for p in data["places"] if "minutes" not in p]
    for place, minutes in zip(untimed, drive_minutes(office, untimed)):
        place["minutes"] = minutes
    in_range = [p for p in data["places"] if p["minutes"] is not None and p["minutes"] <= MAX_MINUTES]
    print(f"timed {len(untimed)} places; dropped {len(data['places']) - len(in_range)} over {MAX_MINUTES} minutes")
    kept = nearest_per_name(in_range)
    print(f"dropped {len(in_range) - len(kept)} farther branches of the same name")

    add_scores(kept)
    data["tier_cuts"] = tier_cuts(kept)
    data["cuisine_groups"] = CUISINE_GROUPS
    ungrouped = sorted({p["cuisine"] for p in kept} - set(CUISINE_GROUPS))
    if ungrouped:
        print(f"cuisines in no group, shown under Other: {', '.join(ungrouped)}")
    data["places"] = sorted(kept, key=lambda p: (p["name"].lower(), p["address"]))
    write_places(PLACES, data)
    print(f"{len(kept)} places written")


if __name__ == "__main__":
    main()
