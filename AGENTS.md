# AGENTS.md

A map of lunch places within a 15-minute drive of the office at 1959 W
Northwest Hwy, Dallas. Live at https://lunch.edgemon.org. `ROADMAP.md` holds
open work.

## Layout

- `www/` is the whole site: `index.html` (Leaflet from unpkg, OpenStreetMap
  tiles, CSS and JS inline) and `places.json`. No build step.
- `update.py` regenerates `places.json`. `tests/` covers the script and checks
  the data.

## Data

```bash
./update.py                 # full refresh; needs GOOGLE_MAPS_API_KEY in .env
./update.py --skip-google   # drive times and scores only, uses no quota
.venv/bin/python -m pytest
```

A full run does four things:

1. Finds restaurants with Google's Nearby Search over a grid of circles
   covering 8 miles around the office. The API returns at most 20 per call, so
   a full circle is split into smaller ones. Each call counts against 1,000
   free a month; the script stops at 800 and prints how many it used.
2. Drops places that are closed, have under 20 reviews, are not open at noon
   on any weekday, or match the fast-food list in `CHAINS`.
3. Gets free-flow drive minutes from the public OSRM server and drops anything
   over 15. These ignore traffic and parking.
4. Scores each place: the Google rating pulled toward the dataset average,
   weighted by review count, so a 4.8 from 30 reviews ranks below a 4.6 from
   3,000.

`notes`, `my_rating` and `hidden` are hand-written per place and survive every
run. `my_rating` replaces the computed score; `hidden: true` removes a place
from the site. The script prints any hand-annotated place that Google no
longer returns instead of dropping it silently.

Storing Google ratings and showing them on a non-Google map are both outside
Google's Places terms. That was a deliberate choice for a small personal site;
the page credits Google Maps and links each place to it.

## Site

The quality tiers (pin color and size) are `TIER_CUTS` in `index.html`. The
blue ramp is one hue, light to dark; keep it that way if the colors change.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
python3 -m http.server -d www 8765   # then open http://127.0.0.1:8765/
```

## Deploy

The homelab playbooks clone this repo to abby and serve `www/`. Push, then from
`~/repos/homelab`: `./deploy.py lunch.edgemon.org`.
