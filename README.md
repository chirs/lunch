# [Lunch Simulator](https://lunch.edgemon.org)

Where to get lunch near the office at 1959 W Northwest Hwy in Dallas. A map of
about 1,900 restaurants within a 23-minute drive, with an estimated quality
score for each and a button that picks one for you. Static site, vanilla
JavaScript, no build step. See [ROADMAP.md](ROADMAP.md) for open work and
[AGENTS.md](AGENTS.md) for the details behind everything below.

## What it does

- **Filters:** a drive-time range, a minimum quality, a cuisine checklist
  (whole groups or single cuisines), price, and visited or shortlisted. "Only
  what's in the map view" limits the list to the visible map.
- **Restaurant card:** click a pin or a row for stat bars, whether it is open
  now, the week's hours, and links to directions, Google Maps and the website.
- **Shortlist:** star a few places; the stars are kept in that browser.
- **Run simulation:** picks a place from the shortlist, or from whatever the
  filters show, leaning toward higher quality. Assuming you leave now, it
  checks that the place is open when you arrive and throughout a 30-, 45-, or
  60-minute meal (45 by default). Places without hours are excluded from picks.
- **Visits:** places you have been to are marked, with your own rating and
  notes in place of the estimates.

## The quality score

The score is the Google rating pulled toward the average of all the places,
weighted by review count. A 4.8 from 30 reviews ranks below a 4.6 from 3,000.
Your own rating replaces it once you have one.

Drive times are free-flow estimates from OSRM. They ignore traffic and
parking, so a lunch-hour drive runs longer than the number shown.

## Data

Everything the site shows is in `www/places.json`, which `update.py` builds:

    ./update.py                               # full refresh; needs GOOGLE_MAPS_API_KEY in .env
    ./update.py --cached                      # re-filter the saved Google results; no API calls
    ./update.py --near 32.9368,-97.0784,1.5   # search 1.5 miles around a point and add the results

A run finds restaurants with Google's Places API, drops what isn't a lunch
option (closed, airport terminals, fast-food chains, under 20 reviews, not
open at noon on a weekday), times the drive from the office, keeps the nearest
branch of each chain, and scores what is left. Cuisine comes from Google's
place type, falling back to words in the name and in Google's summary of the
place when the type is just "restaurant".

A full refresh costs about 1,000 API calls, roughly Google's free monthly
allowance. `--cached` is free and is the one to use for tuning filters.

Notes, ratings, visits and cuisine corrections are written by hand into
`places.json` and survive every refresh.

## Recording a visit

    ./visit.py "hong dumpling"                  # visited, no date
    ./visit.py "hong dumpling" --date today --rating 4.5 --notes "Get the kimchi dumplings."
    ./visit.py "hong dumpling" --undo

Any part of the name works. Commit and deploy afterwards; the site cannot save
visits itself. "Log a visit" on a restaurant's card copies the command.

## Setup

    python3 -m venv .venv && .venv/bin/pip install pytest ruff
    .venv/bin/python -m pytest
    node --test tests/test_app.cjs       # opening-hours logic; needs Node.js
    python3 -m http.server -d www 8765     # then open http://127.0.0.1:8765/

## Deploy

The homelab playbooks clone this repo and serve `www/`. Push, then from the
homelab repo: `./deploy.py lunch.edgemon.org`.

## Credits

Map by [Leaflet](https://leafletjs.com) on
[OpenStreetMap](https://www.openstreetmap.org/copyright) tiles. Ratings,
hours and place details from Google Maps. Drive times from
[OSRM](https://project-osrm.org). Type set in Geist and Geist Mono, under the
SIL Open Font License (`www/fonts/OFL.txt`).

Storing Google's ratings and showing them on a non-Google map are both outside
Google's Places terms; that was a deliberate choice for a small personal site.
