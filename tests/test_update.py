import math
import random

import pytest

import update
from update import (
    add_scores,
    cuisine,
    discover,
    drop_reason,
    haversine_miles,
    hex_grid,
    is_chain,
    merge,
    open_for_lunch,
    split,
    to_record,
)

OFFICE = {"lat": 32.870246, "lon": -96.911634}


def meters(a, b):
    return haversine_miles(*a, *b) * 1609.34


def random_point_within(lat, lon, radius_m, rng):
    distance, angle = radius_m * math.sqrt(rng.random()), rng.random() * 2 * math.pi
    return update.offset(lat, lon, distance * math.cos(angle), distance * math.sin(angle))


def google_place(**overrides):
    place = {
        "id": "abc123",
        "displayName": {"text": "Seoul Garden"},
        "location": {"latitude": 32.895497, "longitude": -96.895566},
        "formattedAddress": "2502 Royal Ln, Dallas, TX 75229, USA",
        "primaryType": "korean_restaurant",
        "businessStatus": "OPERATIONAL",
        "rating": 4.3,
        "userRatingCount": 1200,
        "priceLevel": "PRICE_LEVEL_MODERATE",
        "regularOpeningHours": {"periods": [hours(day, 11, 22) for day in range(7)]},
        "websiteUri": "http://www.dallasseoulgarden.com/",
        "googleMapsUri": "https://maps.google.com/?cid=1",
    }
    place.update(overrides)
    return place


def hours(day, open_hour, close_hour, close_day=None):
    return {
        "open": {"day": day, "hour": open_hour, "minute": 0},
        "close": {"day": day if close_day is None else close_day, "hour": close_hour, "minute": 0},
    }


def test_haversine_same_point():
    assert haversine_miles(32.87, -96.91, 32.87, -96.91) == 0


def test_haversine_one_degree_of_latitude():
    assert haversine_miles(32, -96.91, 33, -96.91) == pytest.approx(69.09, abs=0.05)


def test_hex_grid_covers_the_disc():
    rng = random.Random(1)
    centers = hex_grid(OFFICE["lat"], OFFICE["lon"], 12_000, 1500)
    for _ in range(500):
        point = random_point_within(OFFICE["lat"], OFFICE["lon"], 12_000, rng)
        assert min(meters(point, center) for center in centers) <= 1500 * 1.01


def test_split_covers_the_parent_circle():
    rng = random.Random(2)
    children = split(OFFICE["lat"], OFFICE["lon"], 1500)
    assert len(children) == 7
    assert {radius for _, _, radius in children} == {750}
    for _ in range(500):
        point = random_point_within(OFFICE["lat"], OFFICE["lon"], 1500, rng)
        assert min(meters(point, (lat, lon)) for lat, lon, _ in children) <= 750 * 1.01


def test_discover_splits_full_cells_and_dedupes(monkeypatch):
    monkeypatch.setattr(update, "SEARCH_MILES", 0.5)
    calls = []

    def search(lat, lon, radius):
        calls.append(radius)
        if radius == update.CELL_METERS:  # every top-level cell is full
            return [{"id": f"p{n}"} for n in range(update.PAGE_SIZE)]
        return [{"id": "p0"}, {"id": f"small-{len(calls)}"}]

    found = discover(OFFICE, search)
    top = calls.count(update.CELL_METERS)
    assert calls.count(update.CELL_METERS / 2) == 7 * top
    assert len(found) == update.PAGE_SIZE + 7 * top


def test_discover_stops_at_the_call_cap(monkeypatch):
    monkeypatch.setattr(update, "MAX_CALLS", 3)
    calls = []
    discover(OFFICE, lambda lat, lon, radius: calls.append(radius) or [])
    assert len(calls) == 3


@pytest.mark.parametrize(
    "periods, expected",
    [
        (None, True),
        ([hours(day, 11, 22) for day in range(7)], True),
        ([hours(day, 17, 23) for day in range(7)], False),  # dinner only
        ([hours(0, 11, 15), hours(6, 11, 15)], False),  # weekends only
        ([hours(3, 11, 14)], True),  # one weekday is enough
        ([{"open": {"day": 0, "hour": 0, "minute": 0}}], True),  # open 24 hours
        ([hours(2, 20, 14, close_day=3)], True),  # open overnight through Wednesday noon
        ([hours(6, 22, 13, close_day=1)], True),  # wraps past the end of the week
    ],
)
def test_open_for_lunch(periods, expected):
    place = {"regularOpeningHours": {"periods": periods}} if periods else {}
    assert open_for_lunch(place) is expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("McDonald's", True),
        ("McDonald’s", True),
        ("Sonic Drive-In", True),
        ("Domino's Pizza", True),
        ("Pizza Patrón", True),
        ("Pappasito's Cantina", False),
        ("Keller's Hamburgers", False),
    ],
)
def test_is_chain(name, expected):
    assert is_chain(name) is expected


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, None),
        ({"businessStatus": "CLOSED_PERMANENTLY"}, "closed"),
        ({"location": {"latitude": 33.2, "longitude": -96.9}}, "outside the search area"),
        ({"userRatingCount": 5}, "under 20 reviews"),
        ({"displayName": {"text": "Taco Bell"}}, "fast-food chain"),
        ({"regularOpeningHours": {"periods": [hours(5, 17, 23)]}}, "not open for weekday lunch"),
    ],
)
def test_drop_reason(overrides, expected):
    assert drop_reason(google_place(**overrides), OFFICE) == expected


@pytest.mark.parametrize(
    "primary_type, expected",
    [
        ("korean_restaurant", "Korean"),
        ("middle_eastern_restaurant", "Middle Eastern"),
        ("hamburger_restaurant", "Burgers"),
        ("sandwich_shop", "Sandwiches"),
        ("restaurant", "Other"),
        (None, "Other"),
    ],
)
def test_cuisine(primary_type, expected):
    assert cuisine(primary_type) == expected


def test_to_record():
    assert to_record(google_place()) == {
        "id": "abc123",
        "name": "Seoul Garden",
        "cuisine": "Korean",
        "address": "2502 Royal Ln, Dallas, TX 75229",
        "lat": 32.895497,
        "lon": -96.895566,
        "rating": 4.3,
        "reviews": 1200,
        "maps": "https://maps.google.com/?cid=1",
        "price": "$$",
        "url": "http://www.dallasseoulgarden.com/",
    }


def test_to_record_without_price_or_website():
    place = google_place()
    del place["priceLevel"], place["websiteUri"]
    record = to_record(place)
    assert "price" not in record and "url" not in record


def test_merge_keeps_hand_fields_and_minutes():
    existing = [{"id": "a", "name": "Old name", "minutes": 6.1, "notes": "Get the soup.", "my_rating": 4.8}]
    records, lost = merge(existing, [{"id": "a", "name": "New name"}, {"id": "b", "name": "Other"}])
    assert records[0] == {
        "id": "a",
        "name": "New name",
        "minutes": 6.1,
        "notes": "Get the soup.",
        "my_rating": 4.8,
    }
    assert records[1] == {"id": "b", "name": "Other"}
    assert lost == []


def test_merge_reports_hand_entries_that_vanish():
    existing = [
        {"id": "gone", "name": "Closed Cafe", "notes": "Was good."},
        {"id": "plain", "name": "No notes"},
        {"name": "No id", "notes": "Hand entry."},
    ]
    _, lost = merge(existing, [{"id": "a", "name": "A"}])
    assert [place["name"] for place in lost] == ["Closed Cafe", "No id"]


def test_scores_shrink_toward_the_average():
    places = [
        {"rating": 5.0, "reviews": 10},
        {"rating": 4.5, "reviews": 1000},
        {"rating": 4.0, "reviews": 100},
    ]
    add_scores(places)
    # average 4.5, weight (median reviews) 100
    assert places[0]["score"] == pytest.approx((10 * 5.0 + 100 * 4.5) / 110, abs=0.005)
    assert places[1]["score"] == 4.5
    assert places[2]["score"] == 4.25
    assert places[0]["score"] < 4.6  # ten rave reviews don't beat a thousand good ones by much


def test_my_rating_replaces_the_score():
    places = [{"rating": 4.0, "reviews": 100, "my_rating": 4.9}, {"rating": 4.4, "reviews": 100}]
    add_scores(places)
    assert places[0]["score"] == 4.9


def test_unrated_places_get_no_score():
    places = [{"name": "Hand entry", "score": 4.1}, {"rating": 4.4, "reviews": 100}]
    add_scores(places)
    assert "score" not in places[0]
