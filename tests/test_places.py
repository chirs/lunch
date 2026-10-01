import datetime
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
    if "my_rating" in place:
        assert place["score"] == place["my_rating"], "run update.py --cached"
    if "my_cuisine" in place:
        assert place["cuisine"] == place["my_cuisine"], "run update.py --cached"
    if place.get("visited") not in (None, True):
        datetime.date.fromisoformat(place["visited"])


def test_no_duplicates():
    keys = [p.get("id", p["name"]) for p in PLACE_LIST]
    assert len(keys) == len(set(keys))
