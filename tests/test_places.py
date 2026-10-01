import json

import pytest

from update import MAX_MINUTES, PLACES

DATA = json.loads(PLACES.read_text())
PLACE_LIST = DATA["places"]


@pytest.mark.parametrize("place", PLACE_LIST, ids=lambda p: p.get("name", "?"))
def test_fields(place):
    for field in ("name", "cuisine", "address", "lat", "lon"):
        assert place.get(field), f"missing {field}"
    assert place.get("price", "$") in ("$", "$$", "$$$", "$$$$")
    assert 0 < place["minutes"] <= MAX_MINUTES, "run update.py"
    if "score" in place:
        assert 1 <= place["score"] <= 5


def test_no_duplicates():
    keys = [p.get("id", p["name"]) for p in PLACE_LIST]
    assert len(keys) == len(set(keys))
