import json

import pytest

import lists
import update

OFFICE = {"name": "Office", "address": "1959 W Northwest Hwy", "lat": 32.870246, "lon": -96.911634}


def google_place(id, name, open_hour=11):
    return {
        "id": id,
        "displayName": {"text": name},
        "location": {"latitude": 32.895497, "longitude": -96.895566},
        "formattedAddress": f"{id} Royal Ln, Dallas, TX 75229, USA",
        "primaryType": "korean_restaurant",
        "businessStatus": "OPERATIONAL",
        "rating": 4.3,
        "userRatingCount": 1200,
        "regularOpeningHours": {
            "periods": [
                {"open": {"day": d, "hour": open_hour, "minute": 0}, "close": {"day": d, "hour": 22, "minute": 0}}
                for d in range(7)
            ]
        },
        "googleMapsUri": "https://maps.google.com/?cid=1",
    }


@pytest.fixture
def site(monkeypatch, tmp_path):
    """A site with one lunch place, and saved results that also hold two dinner places."""
    places_path, raw_path = tmp_path / "places.json", tmp_path / "google_raw.json"
    raw = {
        "seoul": google_place("seoul", "Seoul Garden"),
        "nuri": google_place("nuri", "Nuri Steakhouse", open_hour=17),
        "nuri2": google_place("nuri2", "Nuri Grill", open_hour=17),
    }
    raw_path.write_text(json.dumps({"fetched": "2026-09-01", "places": raw}))
    lists_ = {"chris": {"title": "Chris's list", "places": []}, "mark": {"title": "Mark's list", "places": []}}
    places_path.write_text(json.dumps({"office": OFFICE, "lists": lists_, "places": []}))
    monkeypatch.setattr(update, "PLACES", places_path)
    monkeypatch.setattr(update, "RAW", raw_path)
    monkeypatch.setattr(update, "drive_minutes", lambda base, places: [5.0] * len(places))
    monkeypatch.setattr("sys.argv", ["update.py", "--cached"])
    update.main()

    def run(*args):
        monkeypatch.setattr("sys.argv", ["lists.py", *args])
        lists.main()
        return json.loads(places_path.read_text())

    return run


def on_list(data, who="chris"):
    return data["lists"][who]["places"]


def test_adds_a_place_from_the_site(site):
    data = site("chris", "seoul")
    assert on_list(data) == ["seoul"]
    assert on_list(data, "mark") == []
    assert [p["id"] for p in data["places"]] == ["seoul"]
    assert on_list(site("chris", "seoul")) == ["seoul"]  # adding twice changes nothing


def test_adds_a_dropped_place_from_the_saved_results(site):
    data = site("chris", "nuri steak")
    assert on_list(data) == ["nuri"]
    places = {p["id"]: p for p in data["places"]}
    assert places["nuri"]["list_only"] is True
    assert "list_only" not in places["seoul"]


def test_an_ambiguous_name_changes_nothing(site):
    with pytest.raises(SystemExit, match="2 places match"):
        site("chris", "nuri")
    with pytest.raises(SystemExit, match="0 places match"):
        site("chris", "noma")
    assert on_list(site("chris")) == []


def test_remove_drops_a_list_only_place_from_the_site(site):
    site("chris", "nuri steak")
    data = site("chris", "nuri", "--remove")
    assert on_list(data) == []
    assert [p["id"] for p in data["places"]] == ["seoul"]


def test_unknown_list(site):
    with pytest.raises(SystemExit, match="no list 'bob'; there are: chris, mark"):
        site("bob", "seoul")


def test_search_saves_the_top_result_and_lists_it(site, monkeypatch):
    asked = []

    def search(key, query, center):
        asked.append(query)
        return [google_place("maiden", "Maiden", open_hour=17)]

    monkeypatch.setattr(update, "api_key", lambda: "test-key")
    monkeypatch.setattr(lists, "search_text", search)
    data = site("chris", "Maiden Fort Worth", "--search")
    assert asked == ["Maiden Fort Worth"]
    assert on_list(data) == ["maiden"]
    assert {p["id"] for p in data["places"]} == {"seoul", "maiden"}
    assert "maiden" in json.loads(update.RAW.read_text())["places"]


def test_prints_the_list(site, capsys):
    site("chris", "seoul")
    capsys.readouterr()
    site("chris")
    assert capsys.readouterr().out == "Chris's list\n  [ ] Seoul Garden (seoul Royal Ln, Dallas, TX 75229)\n"


def test_several_names_at_once_and_none_if_one_is_wrong(site):
    with pytest.raises(SystemExit, match="0 places match 'noma'"):
        site("chris", "seoul", "noma")
    assert on_list(site("chris")) == []
    assert on_list(site("chris", "nuri steak", "seoul")) == ["nuri", "seoul"]
    assert on_list(site("chris", "seoul", "nuri steak", "--remove")) == []
