import json
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
    nearest_per_name,
    open_for_lunch,
    split,
    tier_cuts,
    to_record,
    week_hours,
    write_places,
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
        "googleMapsUri": "https://maps.google.com/?cid=1&g_mp=CiVnb29nbGU",
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
    calls = []

    def search(lat, lon, radius):
        calls.append(radius)
        if radius == update.CELL_METERS:  # every top-level cell is full
            return [{"id": f"p{n}"} for n in range(update.PAGE_SIZE)]
        return [{"id": "p0"}, {"id": f"small-{len(calls)}"}]

    found = discover(OFFICE, 0.5, search, max_calls=1000)
    top = calls.count(update.CELL_METERS)
    assert calls.count(update.CELL_METERS / 2) == 7 * top
    assert len(found) == update.PAGE_SIZE + 7 * top


def test_discover_stops_at_the_call_cap():
    calls = []
    discover(OFFICE, 8, lambda lat, lon, radius: calls.append(radius) or [], max_calls=3)
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
        ({"formattedAddress": "2400 Aviation Dr, DFW Airport, TX 75261, USA"}, "inside an airport"),
        ({"formattedAddress": "8008 Herb Kelleher Way, Dallas, TX 75235, USA"}, "inside an airport"),
        ({"formattedAddress": "8091 Cedar Springs Rd, Dallas, TX 75235, USA"}, None),
        ({"primaryType": "convenience_store"}, "not a restaurant"),
        ({"primaryType": None}, "not a restaurant"),
        ({"primaryType": "sports_bar"}, None),
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
        ("fast_food_restaurant", "Fast Food"),
        ("taco_restaurant", "Mexican"),
        ("sports_bar", "Bar & Grill"),
        ("diner", "Diner"),
    ],
)
def test_cuisine(primary_type, expected):
    assert cuisine(primary_type) == expected


@pytest.mark.parametrize(
    "primary_type, types, expected",
    [
        # A vague primary type gives way to the first firm cuisine listed.
        ("restaurant", ["restaurant", "mexican_restaurant", "food", "point_of_interest"], "Mexican"),
        ("fast_food_restaurant", ["fast_food_restaurant", "hamburger_restaurant"], "Burgers"),
        # "bar" and "american" are on everything, so a firm cuisine beats them
        # wherever it sits in the list. They still beat nothing.
        ("restaurant", ["bar", "american_restaurant", "seafood_restaurant", "restaurant"], "Seafood"),
        ("restaurant", ["bar", "restaurant"], "Bar & Grill"),
        # Fast Food still beats Other when nothing better is listed.
        ("restaurant", ["fast_food_restaurant", "restaurant", "food"], "Fast Food"),
        ("fast_food_restaurant", ["restaurant", "food"], "Fast Food"),
        # Types that are not about food are ignored.
        ("restaurant", ["restaurant", "food", "store", "establishment"], "Other"),
        # A specific primary type is never overridden.
        ("korean_restaurant", ["mexican_restaurant", "korean_restaurant"], "Korean"),
    ],
)
def test_cuisine_falls_back_to_other_types(primary_type, types, expected):
    assert cuisine(primary_type, types) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Pupuseria Y Antojitos", "Salvadoran"),
        ("El Olanchano restaurante hondureño", "Honduran"),
        ("La Campiña Salvadoreña", "Salvadoran"),
        ("Sabor Llanero TX", "Venezuelan"),
        ("Mi Sabor Latino", "Latin American"),
        ("El Amigo Taqueria (Maple)", "Mexican"),
        ("Sophia's Cocina Y Cantina", "Mexican"),
        ("Roland's Jamaica Chicken", "Caribbean"),
        ("WING CASTLE", "Chicken"),
        ("Kabab Kurry N More", "Indian"),
        ("Pho MC", "Vietnamese"),
        ("Big Tony's Hot Cheese Steak & Wings", "Sandwiches"),
        ("JW Steakhouse", "Steakhouse"),
        ("Sweet Paris Crêperie & Café", "Breakfast"),
        ("Hudson House", "Other"),
        ("Phoenix Room", "Other"),  # "pho" only counts as a whole word
    ],
)
def test_cuisine_falls_back_to_the_name(name, expected):
    assert cuisine("restaurant", ["restaurant", "food"], name) == expected


def test_the_name_beats_a_listed_type():
    # Both of these came out wrong when the type list was trusted first.
    assert cuisine("restaurant", ["bar", "restaurant"], "El Peñon Restaurante Salvadoreño") == "Salvadoran"
    assert cuisine("fast_food_restaurant", ["chicken_restaurant", "hamburger_restaurant"], "Whataburger") == "Burgers"


@pytest.mark.parametrize(
    "summary, expected",
    [
        ("Upscale Indian restaurant with a lakeside patio and inventive cocktails.", "Indian"),
        ("Steaks and seafood in a clubby, wood-paneled setting.", "Steakhouse"),  # earliest word wins
        ("Casual spot for Tex-Mex fare and margaritas.", "Mexican"),
        ("Relaxed counter-serve joint for Southern comfort food.", "Southern"),
        ("Hotel dining room serving comfort food and cocktails.", "American"),
        ("French-inspired bakery chain with quiche and sandwiches.", "French"),
        ("Lively hangout with a patio.", None),
        ("", None),
        # Real summaries that an earlier version of the rules got wrong.
        ("Yemeni eatery with a menu of familiar dishes, including lamb and chicken entrees.", "Middle Eastern"),
        ("Central American/El Salvadorean cafe for dishes such as pupusas and tacos.", "Salvadoran"),
        ("Big portions of Latin comfort food including Dominican classics.", "Latin American"),
        ("Casual restaurant serving Venezuelan comfort food including arepas, plus desserts.", "Venezuelan"),
        ("Casual venue for breakfast, lunch, and dinner, including popular Honduran dishes.", "Honduran"),
        ("Relaxed eatery dishing up comfort food such as fajitas.", "Mexican"),
        ("Easygoing gastropub offering wood-fired pizza, American fare & many wines.", "American"),
        ("Roomy brewpub at the Gaylord Texan Hotel for burgers, beer & sports.", "Bar & Grill"),
        ("Casual eatery specializing in baked potatoes, chicken and steak.", "American"),
        ("Organic coffee drinks & breakfast bites like avocado toast.", "Cafe"),
        ("Down-to-earth restaurant serving all-day breakfast, sandwiches & toasts.", "Breakfast"),
    ],
)
def test_summary_hint(summary, expected):
    assert update.summary_hint(summary) == expected


def test_share_cuisines_fills_in_other_branches():
    records = [
        {"name": "Hudson House", "cuisine": "Seafood"},
        {"name": "Hudson House", "cuisine": "Other"},
        {"name": "Monaco", "cuisine": "Other"},
        {"name": "Original ChopShop", "cuisine": "Salads"},
        {"name": "Original ChopShop", "cuisine": "Cafe"},
        {"name": "Original ChopShop", "cuisine": "Salads"},
        {"name": "Original ChopShop", "cuisine": "Other"},
    ]
    update.share_cuisines(records)
    assert [r["cuisine"] for r in records] == ["Seafood", "Seafood", "Other", "Salads", "Cafe", "Salads", "Salads"]


def test_cuisine_uses_the_summary_last():
    summary = "Upscale Indian restaurant."
    assert cuisine("restaurant", ["restaurant"], "Sanjh Restaurant & Bar", summary) == "Indian"
    assert cuisine("restaurant", ["thai_restaurant"], "Sanjh", summary) == "Thai"
    assert cuisine("restaurant", ["restaurant"], "Sanjh Taqueria", summary) == "Mexican"


def test_summary_text_prefers_the_editorial_line():
    both = {
        "editorialSummary": {"text": "Editors' line."},
        "generativeSummary": {"overview": {"text": "Generated line."}},
    }
    assert update.summary_text(both) == "Editors' line."
    assert update.summary_text({"generativeSummary": {"overview": {"text": "Generated line."}}}) == "Generated line."
    assert update.summary_text({}) == ""


def test_add_summaries_asks_once_and_only_for_other_places(capsys):
    places = {
        "vague": google_place(id="vague", primaryType="restaurant", displayName={"text": "Hudson House"}),
        "known": google_place(id="known"),
        "closed": google_place(id="closed", primaryType="restaurant", businessStatus="CLOSED_PERMANENTLY"),
    }
    asked = []

    def details(place_id):
        asked.append(place_id)
        return {"editorialSummary": {"text": "Oysters and American classics."}}

    update.add_summaries(places, OFFICE, details, max_calls=10)
    update.add_summaries(places, OFFICE, details, max_calls=10)
    assert asked == ["vague"]
    assert update.place_cuisine(places["vague"]) == "Seafood"
    assert "summary" not in places["known"]


def test_the_name_beats_fast_food():
    assert cuisine("fast_food_restaurant", ["fast_food_restaurant"], "Laredo Taco Company") == "Mexican"


def test_each_cuisine_is_in_one_group():
    listed = [cuisine for cuisines in update.GROUPS.values() for cuisine in cuisines]
    assert len(listed) == len(set(listed))
    assert update.CUISINE_GROUPS["Korean"] == "Asian"


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
        "hours": ["1100-2200"] * 7,
    }


def test_week_hours():
    lunch_and_dinner = [hours(1, 17, 22), hours(1, 11, 14), hours(5, 17, 2, close_day=6)]
    place = {"regularOpeningHours": {"periods": lunch_and_dinner}}
    assert week_hours(place) == ["", "1100-1400,1700-2200", "", "", "", "1700-0200", ""]


def test_week_hours_always_open_and_unlisted():
    always = {"regularOpeningHours": {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}}
    assert week_hours(always) == ["0000-2400"] * 7
    assert week_hours({}) is None


def test_write_places_round_trips_one_place_per_line(tmp_path):
    data = {
        "office": {"name": "Office"},
        "places": [{"name": "Pizza Patrón", "hours": ["", "1100-2200"]}, {"name": "B"}],
        "tier_cuts": [4.3, 4.5],
    }
    path = tmp_path / "places.json"
    write_places(path, data)
    text = path.read_text()
    assert json.loads(text) == data
    assert '{"name":"Pizza Patrón","hours":["","1100-2200"]},\n{"name":"B"}\n' in text


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


def test_nearest_per_name_keeps_the_closest_branch():
    places = [
        {"name": "Whataburger", "minutes": 9.0},
        {"name": "Whataburger", "minutes": 4.0},
        {"name": "Keller's Drive-In", "minutes": 7.0},
    ]
    assert nearest_per_name(places) == [places[1], places[2]]


def test_nearest_per_name_keeps_hand_annotated_branches():
    places = [
        {"name": "Mi Cocina", "minutes": 12.0, "notes": "The one with the patio."},
        {"name": "Mi Cocina", "minutes": 6.0},
    ]
    assert nearest_per_name(places) == places


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


def test_tier_cuts_put_a_fifth_in_each_outer_tier():
    scores = [4.0] * 5 + [4.1] * 15 + [4.2] * 30 + [4.3] * 30 + [4.4] * 12 + [4.5] * 8
    assert tier_cuts([{"score": s} for s in scores]) == [4.2, 4.4]


def test_tier_cuts_use_the_score_as_displayed():
    assert tier_cuts([{"score": s} for s in (4.04, 4.16, 4.24, 4.31, 4.38)]) == [4.2, 4.4]


def test_my_rating_replaces_the_score():
    places = [{"rating": 4.0, "reviews": 100, "my_rating": 4.9}, {"rating": 4.4, "reviews": 100}]
    add_scores(places)
    assert places[0]["score"] == 4.9


def test_unrated_places_get_no_score():
    places = [{"name": "Hand entry", "score": 4.1}, {"rating": 4.4, "reviews": 100}]
    add_scores(places)
    assert "score" not in places[0]
