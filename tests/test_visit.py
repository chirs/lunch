import datetime
import json

import pytest

import visit
from visit import find_places, parse_date, parse_rating, record_visit

PLACES = [
    {"name": "Hong Dumpling House", "address": "1901 Royal Ln", "rating": 4.9, "reviews": 958},
    {"name": "Keller’s Drive-In", "address": "10226 Harry Hines Blvd", "rating": 4.4, "reviews": 1880},
    {"name": "Pappas Bar-B-Q", "address": "2231 W Northwest Hwy", "rating": 4.1, "reviews": 2310},
    {"name": "Pappasitos Cantina", "address": "10433 Lombardy Ln", "rating": 4.5, "reviews": 6490},
    {"name": "Monaco", "address": "5238 N O'Connor Blvd", "rating": 4.7, "reviews": 517},
    {"name": "Monaco Pizza", "address": "1 Main St", "rating": 4.0, "reviews": 100},
]


def names(places):
    return [p["name"] for p in places]


def test_find_by_part_of_the_name():
    assert names(find_places(PLACES, "hong dump")) == ["Hong Dumpling House"]


def test_find_ignores_case_and_punctuation():
    assert names(find_places(PLACES, "KELLER'S drive in")) == ["Keller’s Drive-In"]


def test_exact_name_beats_longer_names_containing_it():
    assert names(find_places(PLACES, "monaco")) == ["Monaco"]


def test_ambiguous_and_missing_names():
    assert names(find_places(PLACES, "pappas")) == ["Pappas Bar-B-Q", "Pappasitos Cantina"]
    assert find_places(PLACES, "noma") == []


def test_parse_date():
    assert parse_date("2026-10-01") == "2026-10-01"
    assert parse_date("today") == datetime.datetime.now().astimezone().date().isoformat()
    with pytest.raises(ValueError):
        parse_date("10/1/2026")


def test_parse_rating():
    assert parse_rating("4.5") == 4.5
    with pytest.raises(ValueError):
        parse_rating("7")


def test_visit_without_a_date():
    place = {"name": "Monaco", "notes": "Upscale, on the water."}
    record_visit(place)
    assert place == {"name": "Monaco", "notes": "Upscale, on the water.", "visited": True}


def test_visit_with_everything():
    place = {"name": "Monaco", "notes": "Upscale, on the water."}
    record_visit(place, date="2026-10-01", rating=4.5, notes="Great patio.")
    assert place == {"name": "Monaco", "notes": "Great patio.", "visited": "2026-10-01", "my_rating": 4.5}


def test_undated_revisit_keeps_the_earlier_date():
    place = {"name": "Monaco", "visited": "2026-10-01"}
    record_visit(place)
    assert place["visited"] == "2026-10-01"


def run(monkeypatch, tmp_path, *args):
    path = tmp_path / "places.json"
    if not path.exists():
        path.write_text(json.dumps({"office": {}, "places": [dict(p) for p in PLACES]}))
    monkeypatch.setattr(visit, "PLACES", path)
    monkeypatch.setattr("sys.argv", ["visit.py", *args])
    visit.main()
    return {p["name"]: p for p in json.loads(path.read_text())["places"]}


def test_main_records_the_visit_and_rescores(monkeypatch, tmp_path):
    places = run(monkeypatch, tmp_path, "hong", "--date", "2026-10-01", "--rating", "4.8", "--notes", "Go early.")
    hong = places["Hong Dumpling House"]
    assert (hong["visited"], hong["my_rating"], hong["notes"], hong["score"]) == ("2026-10-01", 4.8, "Go early.", 4.8)
    assert "visited" not in places["Monaco"]


def test_main_undo_clears_only_the_visit(monkeypatch, tmp_path):
    run(monkeypatch, tmp_path, "hong", "--rating", "4.8")
    hong = run(monkeypatch, tmp_path, "hong", "--undo")["Hong Dumpling House"]
    assert "visited" not in hong and hong["my_rating"] == 4.8


def test_main_refuses_an_ambiguous_name(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="2 places match 'pappas'"):
        run(monkeypatch, tmp_path, "pappas")
