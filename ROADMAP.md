# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Make a full run search the right area: build the grid from cells whose centers are within the 23-minute cap (OSRM is free) and pass it to `search_cells()`, instead of a 14-mile circle that wastes calls on unreachable land; the 20 to 23 minute band has never been searched on purpose
- [ ] With that in place, rerun the fetch to pick up the less popular places in dense spots; the runs so far stopped at their call caps with several hundred small cells unsearched
- [ ] Replace the seed notes with real reviews as places get visited (`visit.py`)
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Deferred

- Group voting: needs a backend and shared state; the site is static.
