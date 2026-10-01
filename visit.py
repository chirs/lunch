#!/usr/bin/env python3
"""Record a visit in www/places.json.

    ./visit.py "hong dumpling"                  # visited, no date
    ./visit.py "hong dumpling" --date today
    ./visit.py "hong dumpling" --date 2026-10-01 --rating 4.5 --notes "Get the kimchi dumplings."
    ./visit.py "hong dumpling" --undo           # clear the visit; notes and rating stay

Any part of the place's name will do. The rating replaces the estimated score
and the notes replace whatever notes were there. Commit, push and deploy after.
"""

import argparse
import datetime
import json
import re
import sys

from update import PLACES, add_scores, write_places


def plain(text):
    words = re.sub(r"[^a-z0-9 ]", "", text.casefold().replace("-", " "))
    return " ".join(words.split())


def find_places(places, query):
    """Places whose name is the query, or failing that, contains it."""
    wanted = plain(query)
    exact = [p for p in places if plain(p["name"]) == wanted]
    return exact or [p for p in places if wanted in plain(p["name"])]


def parse_date(text):
    if text == "today":
        return datetime.datetime.now().astimezone().date().isoformat()
    return datetime.date.fromisoformat(text).isoformat()


def parse_rating(text):
    rating = float(text)
    if not 1 <= rating <= 5:
        raise ValueError(text)
    return rating


def record_visit(place, date=None, rating=None, notes=None):
    """A visit with no date keeps the date of an earlier one."""
    place["visited"] = date or place.get("visited") or True
    if rating is not None:
        place["my_rating"] = rating
    if notes is not None:
        place["notes"] = notes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="any part of the place's name")
    parser.add_argument("--date", type=parse_date, help="YYYY-MM-DD or 'today'")
    parser.add_argument("--rating", type=parse_rating, help="your rating, 1 to 5")
    parser.add_argument("--notes", help="your review")
    parser.add_argument("--undo", action="store_true", help="clear the visit")
    args = parser.parse_args()

    data = json.loads(PLACES.read_text())
    matches = find_places(data["places"], args.name)
    if len(matches) != 1:
        listing = "\n".join(f"  {p['name']} ({p['address']})" for p in matches[:15])
        sys.exit(f"{len(matches)} places match {args.name!r}; be more specific\n{listing}".rstrip())
    place = matches[0]

    if args.undo:
        place.pop("visited", None)
    else:
        record_visit(place, args.date, args.rating, args.notes)
    add_scores(data["places"])
    write_places(PLACES, data)

    shown = {k: place[k] for k in ("visited", "my_rating", "notes", "score") if k in place}
    print(f"{place['name']}: {shown}")


if __name__ == "__main__":
    main()
