# AGENTS.md

A map of lunch places within a short drive of the office at 1959 W Northwest
Hwy, Dallas. Live at https://lunch.edgemon.org. `ROADMAP.md` holds open work.

## Layout

- `www/` is the whole site: `index.html` (Leaflet from unpkg, OpenStreetMap
  tiles, CSS and JS inline) and `places.json`. No build step.
- `geocode.py` fills in coordinates. `tests/` checks the data.

## Adding or changing a place

`www/places.json` is hand-curated. Add an entry with `name`, `cuisine`,
`address` and `price` (`$`, `$$` or `$$$`); `notes` and `url` are optional.
Leave out `lat` and `lon`, then:

```bash
./geocode.py                    # fills missing coordinates from the address
.venv/bin/python -m pytest      # fields present, no duplicates, within 5 miles
```

Never type coordinates from memory. If Nominatim has no match, find the place
on openstreetmap.org and copy its coordinates.

`cuisine` is the filter chip, so keep it to one broad word that other entries
share (`Mexican`, not `Tex-Mex`); put the detail in `notes`.

The first list came from OpenStreetMap and web search on 2026-10-01, with
price tiers guessed. Nobody had eaten at these for the site, so treat entries
without a personal note as unvetted.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
python3 -m http.server -d www 8765   # then open http://127.0.0.1:8765/
```

## Deploy

The homelab playbooks clone this repo to abby and serve `www/`. Push, then from
`~/repos/homelab`: `./deploy.py lunch.edgemon.org`.
