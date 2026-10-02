# AGENTS.md

Lunch Simulator: a map of lunch places within a 23-minute drive of the office
at 1959 W Northwest Hwy, Dallas. Live at https://lunch.edgemon.org. `ROADMAP.md` holds
open work.

## Layout

- `www/` is the whole site: `index.html`, `style.css`, `app.js` and
  `places.json`. Leaflet comes from unpkg and the tiles from OpenStreetMap.
  No build step.
- `update.py` regenerates `places.json`. `tests/` covers the script and checks
  the data.

## Data

```bash
./update.py            # full refresh; needs GOOGLE_MAPS_API_KEY in .env
./update.py --cached   # no Google calls; re-filters the saved results
./update.py --near 32.9368,-97.0784,1.5   # top up: search 1.5 miles around a point
.venv/bin/python -m pytest
```

A full run costs about 1,000 Google calls, so use `--cached` for everything
else: tuning the filters, recomputing scores after adding a `my_rating`. It
reads `google_raw.json`, which a full run writes and git ignores. On a clone
without that file, `--cached` leaves the list alone and only redoes drive times
and scores.

A full run does five things:

1. Finds restaurants with Google's Nearby Search over a grid of circles
   covering 14 miles around the office. The API returns at most 20 per call, so
   a full circle is split into smaller ones. This pass stops at 800 calls;
   1,000 a month are free.
2. Makes a second pass for bar types, capped at 200 calls, keeping the ones
   Google says serve lunch. Icehouses and sports bars often lack the
   "restaurant" type and the first pass misses them. Asking for `servesLunch`
   bills as a different SKU with its own 1,000 free calls.
3. Drops places that are closed, are inside an airport (DFW's zip 75261 and
   the Love Field terminal's addresses; see `AIRPORTS`), are not really
   restaurants (Google tags gas
   stations and smoothie shops as restaurants; see `LUNCH_TYPES`), have under
   20 reviews, are not open at noon on any weekday, or match the fast-food
   list in `CHAINS`.
4. Gets free-flow drive minutes from the public OSRM server, drops anything
   over `MAX_MINUTES` (23), and keeps only the nearest branch of each name.
   These times ignore traffic and parking. The cap is written to `places.json`
   as `max_minutes`, which is where the site's sliders get their range.
5. Scores each place: the Google rating pulled toward the dataset average,
   weighted by review count, so a 4.8 from 30 reviews ranks below a 4.6 from
   3,000.

Coverage, as of 2026-10-01. The data was built in three fetches the same day:

- The full run searched 8 miles out and hit both call caps, so the densest
  spots are missing their less popular places. Bachman Tacos & Grill is a
  known miss.
- The limit then went from 15 to 20 minutes, which reaches 9 to 12 miles along
  the freeways. Downtown Grapevine (16 to 18 minutes) was entirely missing and
  was topped up with `--near`: 77 restaurant calls and 14 bar calls.
- An audit against OpenStreetMap found 42 grid cells reachable in 20 minutes
  that had never been searched. A one-off run searched 39 of them (not the
  airport, and not downtown Dallas or Carrollton's Old Denton Road, which the
  first run's overlap had covered well) plus the Addison Belt Line strip. It
  stopped at 230 restaurant calls with 201 small cells still queued.

So every area reachable in 20 minutes has at least its 20 most popular places,
and the gaps that remain there are the less popular places in dense spots.
October's calls on the ratings tier came to about 1,110 against 1,000 free.

The cap then went from 20 to 23 minutes with no new search, to bring in places
just past the line at Grapevine Mills, far north Dallas and south Lewisville.
The 20 to 23 minute band therefore holds only what the earlier searches
happened to catch, and has not been audited.

`--near` is the cheap way to fill a known hole: it searches a small circle,
adds the results to `google_raw.json`, and reruns the rest. `search_cells()`
takes an explicit list of circles when a hex grid around one point is not the
right shape.

Each place's `cuisine` comes from Google's primary type (`CUISINES` renames
and merges a few). Google calls about a quarter of places just "restaurant",
so `cuisine()` falls back, in order of trust, to a telling word in the name
(`NAME_HINTS`), then the place's other Google types, then a telling word in
Google's written summary of the place (`SUMMARY_HINTS`), then Fast Food. Name
before types is deliberate: the type lists are not in order of relevance and
put Whataburger under Chicken and a pupuseria under Bar & Grill. A branch
still left as Other then takes the cuisine of its same-named branches
(`share_cuisines()`).

Only 69 of the 122 places asked about had a summary at all, which left 54 as
Other. Nine of those (Sanjh, Lions Den, Casa Brasa and others) were given a
`my_cuisine` by hand from D Magazine on 2026-10-01, and the owner labeled the
last 44 himself the same day, hiding four that are not lunch places. Nothing
is Other now; a refresh will bring new ones, which `my_cuisine` can settle.

The owner's labels introduced Honduran, Nicaraguan, Guatemalan and Venezuelan,
so the name and summary rules now name the country where they can (a
pupuseria is Salvadoran) and keep Latin American for the general case.

D Magazine cannot be used as a dataset. Its directory sits behind a bot
challenge and its robots file disallows Anthropic's crawler, so nothing there
was fetched. The nine came from search-engine results for dmagazine.com, one
restaurant at a time, checked against the address. That works for the places
D has written about (11 of the 30 tried) and not for small ones.

A full fetch asks for `types`, and any fetch then looks up a summary for each
place still Other (`add_summaries()`, Place Details with `editorialSummary`
and `generativeSummary`, a tier with 1,000 free a month). It saves the answer
even when empty, so nothing is asked twice. The saved results from 2026-10-01
predate the `types` field, so the places that needed it were backfilled one at
a time through Place Details (field mask `types`, the Essentials tier, 10,000
free a month).

`GROUPS` sorts the cuisines into the groups of the site's cuisine checklist. A
cuisine in no group shows under Other, and a run prints any it finds.

`hours` is seven strings, Sunday first, such as `1100-1400,1700-2200`; a range
that runs past midnight stays on the day it opens. `places.json` holds one
place per line, which keeps it small and keeps diffs to the places that
changed.

`notes`, `my_rating`, `my_cuisine`, `visited` and `hidden` are hand-written per
place and survive every run. `my_rating` replaces the computed score and
`my_cuisine` the computed cuisine; `visited` is `true` or a `YYYY-MM-DD` date;
`hidden: true` removes a place from the site. The
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

The look is dark and calm: a flush panel beside the map, Geist for text and
Geist Mono for labels and readouts (both self-hosted in `www/fonts/`), and one
soft seafoam for data and the main action. It took three tries on 2026-10-01:
a retro management-sim skin was "corny", a white clean-SaaS panel was "super
generic", and a neon lime version of this dark look was "too aggressive".
Keep the accent quiet.

The map uses the standard OpenStreetMap tiles, inverted and drained of color
with a CSS filter. CARTO's dark basemap would be cleaner but needs an API key.

Filters: a drive-time range (shortest and longest), a quality slider, a
cuisine checklist, price toggles, visited/shortlist, and sort. The drive-time
range is two native range inputs stacked so that only their thumbs take
clicks; dragging and arrow keys work, clicking the bare track does not. The checklist ticks whole groups (`GROUPS` in
`update.py`) or opens a group to tick single cuisines; ticking several means
"any of these". Price toggles work the same way, and a place with no price
from Google drops out once any price is picked. "Only what's in the map
view" limits the list, the counts and the simulation to the visible map and
follows it as it moves; the pins are not limited, so panning still finds them,
and the drive-time thumbs stop reframing the map while it is on.

On a phone or a window under 700px tall the filters start folded behind one
bar that reads out what is set ("4 to 14 min · 4.3+ · Asian · $ $$"), so the
list gets the room. Taller desktop windows always show them.

Clicking a pin or a row opens the restaurant card in place of the controls and
list: stat bars, an open-now chip, links, a shortlist toggle, and "Log a
visit", which shows and copies the `visit.py` command because the page cannot
write visits itself. The shortlist lives in that browser's local storage. "Run
simulation" picks from the shortlist when it holds two or more places,
otherwise from what the filters show, weighted toward higher scores.

The quality tiers (pin color and size) are cut at `tier_cuts` in
`places.json`, which `update.py` sets so each outer tier holds about a fifth of
the places. The pin ramp is one hue, dim to bright, because on a dark map the
brightest reads as the most; keep it one hue if the colors change.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
python3 -m http.server -d www 8765   # then open http://127.0.0.1:8765/
```

## Deploy

The homelab playbooks clone this repo to abby and serve `www/`. Push, then from
`~/repos/homelab`: `./deploy.py lunch.edgemon.org`.
