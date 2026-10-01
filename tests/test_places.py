import json

import pytest

from geocode import PLACES, haversine_miles, street_address

DATA = json.loads(PLACES.read_text())
OFFICE = DATA["office"]
PLACE_LIST = DATA["places"]
MAX_MILES = 5


@pytest.mark.parametrize("place", PLACE_LIST, ids=lambda p: p.get("name", "?"))
def test_required_fields(place):
    for field in ("name", "cuisine", "address"):
        assert place.get(field), f"missing {field}"
    assert place.get("price") in ("$", "$$", "$$$")


def test_no_duplicate_names():
    names = [p["name"] for p in PLACE_LIST]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("place", PLACE_LIST, ids=lambda p: p.get("name", "?"))
def test_geocoded_near_office(place):
    assert "lat" in place and "lon" in place, "run geocode.py"
    miles = haversine_miles(OFFICE["lat"], OFFICE["lon"], place["lat"], place["lon"])
    assert miles <= MAX_MILES, f"{miles:.1f} mi from the office; bad geocode?"


def test_haversine_same_point():
    assert haversine_miles(32.87, -96.91, 32.87, -96.91) == 0


def test_haversine_one_degree_of_latitude():
    assert haversine_miles(32, -96.91, 33, -96.91) == pytest.approx(69.09, abs=0.05)


@pytest.mark.parametrize(
    "address",
    [
        "1901 Royal Ln #105, Dallas, TX 75229",
        "1901 Royal Ln Ste 105, Dallas, TX 75229",
        "1901 Royal Ln Suite 105, Dallas, TX 75229",
    ],
)
def test_street_address_drops_suite(address):
    assert street_address(address) == "1901 Royal Ln, Dallas, TX 75229"


def test_street_address_keeps_plain_address():
    address = "2231 W Northwest Hwy, Dallas, TX 75220"
    assert street_address(address) == address
