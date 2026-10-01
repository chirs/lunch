# AGENTS.md

A map of lunch places within a 20-minute drive of the office at 1959 W
Northwest Hwy, Dallas. Live at https://lunch.edgemon.org. `ROADMAP.md` holds
open work.

## Layout

- `www/` is the whole site: `index.html` (Leaflet from unpkg, OpenStreetMap
  tiles, CSS and JS inline) and `places.json`. No build step.
- `update.py` regenerates `places.json`. `tests/` covers the script and checks
  the data.

## Data

```bash
./update.py            # full refresh; needs GOOGLE_MAPS_API_KEY in .env
./update.py --cached   # no Google calls; re-filters the saved results
.venv/bin/python -m pytest
```

A full run costs about 1,000 Google calls, so use `--cached` for everything
else: tuning the filters, recomputing scores after adding a `my_rating`. It
reads `google_raw.json`, which a full run writes and git ignores. On a clone
without that file, `--cached` leaves the list alone and only redoes drive times
and scores.

A full run does five things:

1. Finds restaurants with Google's Nearby Search over a grid of circles
   covering 12 miles around the office. The API returns at most 20 per call, so
   a full circle is split into smaller ones. This pass stops at 800 calls;
   1,000 a month are free.
2. Makes a second pass for bar types, capped at 200 calls, keeping the ones
   Google says serve lunch. Icehouses and sports bars often lack the
   "restaurant" type and the first pass misses them. Asking for `servesLunch`
   bills as a different SKU with its own 1,000 free calls.
3. Drops places that are closed, are not really restaurants (Google tags gas
   stations and smoothie shops as restaurants; see `LUNCH_TYPES`), have under
   20 reviews, are not open at noon on any weekday, or match the fast-food
   list in `CHAINS`.
4. Gets free-flow drive minutes from the public OSRM server, drops anything
   over 20, and keeps only the nearest branch of each name. These times ignore
   traffic and parking.
5. Scores each place: the Google rating pulled toward the dataset average,
   weighted by review count, so a 4.8 from 30 reviews ranks below a 4.6 from
   3,000.

Both passes hit their caps on the first run (2026-10-01), so the densest spots
are missing their less popular places. Bachman Tacos & Grill is a known miss.
That run also searched only 8 miles out, before the limit went from 15 to 20
minutes. The 20-minute reach is 9 to 12 miles along the freeways, so beyond 8
miles the list holds only what spilled over from the edge cells.

`notes`, `my_rating`, `visited` and `hidden` are hand-written per place and
survive every run. `my_rating` replaces the computed score; `visited` is `true`
or a `YYYY-MM-DD` date; `hidden: true` removes a place from the site. The
script prints any hand-annotated place that Google no longer returns instead
of dropping it silently.

Record a visit with `visit.py`, then commit, push and deploy:

```bash
./visit.py "hong dumpling"                  # visited, no date
./visit.py "hong dumpling" --date today --rating 4.5 --notes "Get the kimchi dumplings."
./visit.py "hong dumpling" --undo           # clears the visit, keeps notes and rating
```

Any part of the name works; an ambiguous name lists the candidates and changes
nothing. `--notes` is the review and overwrites the existing notes.

Storing Google ratings and showing them on a non-Google map are both outside
Google's Places terms. That was a deliberate choice for a small personal site;
the page credits Google Maps and links each place to it.

## Site

The quality tiers (pin color and size) are cut at `tier_cuts` in
`places.json`, which `update.py` sets so each outer tier holds about a fifth of
the places. The blue ramp is one hue, light to dark; keep it that way if the
colors change.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
python3 -m http.server -d www 8765   # then open http://127.0.0.1:8765/
```

## Deploy

The homelab playbooks clone this repo to abby and serve `www/`. Push, then from
`~/repos/homelab`: `./deploy.py lunch.edgemon.org`.
