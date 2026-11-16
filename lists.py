#!/usr/bin/env python3
"""Put a place on somebody's list in www/places.json.

    ./lists.py chris                               # print the list
    ./lists.py chris "nuri" "claremont"            # add: any part of each name
    ./lists.py chris "Maiden Fort Worth" --search  # add a place Google has to be asked for
    ./lists.py chris "nuri" --remove

A name is looked for among the site's places, then in the saved Google results
(google_raw.json), which hold the places the lunch rules dropped. --search
makes one Google Text Search call per name and takes the top result, so say
the town when the name is common. Several names in one go cost one rebuild. A listed place stays on the site whatever its hours
or distance. Commit, push and deploy after.
"""

import argparse
import json
import sys
import urllib.request

import update
from visit import find_places

SEARCH_METERS = 50_000  # Text Search leans toward this circle around the office; it is not a limit


def search_text(key, query, center):
    body = {
        "textQuery": query,
        "pageSize": 1,
        "locationBias": {
            "circle": {
                "center": {"latitude": center["lat"], "longitude": center["lon"]},
                "radius": SEARCH_METERS,
            }
        },
    }
    request = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": update.FIELD_MASK,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("places", [])


def saved_places(raw):
    return [
        {"id": id, "name": place["displayName"]["text"], "address": place.get("formattedAddress", "")}
        for id, place in raw["places"].items()
    ]


def find(places, raw, query):
    """Matches on the site, or failing that, among everything Google returned."""
    return find_places(places, query) or find_places(saved_places(raw), query)


def one(matches, query):
    if len(matches) != 1:
        listing = "\n".join(f"  {p['name']} ({p['address']})" for p in matches[:15])
        sys.exit(f"{len(matches)} places match {query!r}; be more specific\n{listing}".rstrip())
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("list", help="whose list, as named under lists in places.json")
    parser.add_argument("names", nargs="*", metavar="name", help="any part of a place's name; none prints the list")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--search", action="store_true", help="ask Google for each place: one Text Search call each")
    action.add_argument("--remove", action="store_true", help="take the places off the list")
    args = parser.parse_args()

    data = json.loads(update.PLACES.read_text())
    lists = data.get("lists", {})
    if args.list not in lists:
        sys.exit(f"no list {args.list!r}; there are: {', '.join(lists) or 'none'}")
    title, ids = lists[args.list]["title"], lists[args.list]["places"]
    by_id = {p.get("id"): p for p in data["places"]}

    if not args.names:
        print(title)
        for id in ids:
            place = by_id.get(id)
            mark = "x" if place and place.get("visited") else " "
            print(f"  [{mark}] {place['name']} ({place['address']})" if place else f"  [ ] not found: {id}")
        return

    # Every name is settled before anything is written, so a bad one changes nothing.
    if args.remove:
        on_list = [by_id[id] for id in ids if id in by_id]
        chosen = [one(find_places(on_list, name), name) for name in args.names]
    elif args.search:
        # Without the saved results a rebuild would take these places for the whole fetch.
        if not update.RAW.exists():
            sys.exit("--search adds to google_raw.json, which is missing here")
        key, found = update.api_key(), {}
        for name in args.names:
            results = search_text(key, name, data["office"])
            if not results:
                sys.exit(f"Google found nothing for {name!r}")
            found[results[0]["id"]] = results[0]
        raw = json.loads(update.RAW.read_text())
        for id, place in found.items():
            raw["places"][id] = {**raw["places"].get(id, {}), **place}
        update.RAW.write_text(json.dumps(raw))
        chosen = saved_places({"places": found})
    else:
        raw = json.loads(update.RAW.read_text()) if update.RAW.exists() else {"places": {}}
        chosen = [one(find(data["places"], raw, name), name) for name in args.names]
    for place in chosen:
        if args.remove:
            ids.remove(place["id"])
        elif place["id"] not in ids:
            ids.append(place["id"])

    update.rebuild(data, [data[base] for base in ("office", "home") if base in data])
    print(f"{'removed from' if args.remove else 'on'} {title}:")
    for place in chosen:
        print(f"  {place['name']} ({place['address']})")


if __name__ == "__main__":
    main()
