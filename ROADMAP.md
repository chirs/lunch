# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Rerun the Google fetch: the first run searched only 8 miles out, so the 15 to 20 minute band is thin past that (downtown Grapevine aside), and it stopped at its call caps with 716 restaurant cells and 70 bar cells unsearched
- [ ] Before that rerun, skip grid cells whose centers are more than 20 minutes away (OSRM is free); a 12-mile grid is about 200 top-level cells against a cap of 800 calls
- [ ] Replace the seed notes with real reviews as places get visited (`visit.py`)
- [ ] Break up the "Other" group (368 places, most of which Google only calls "restaurant"): ask for `types` on the next fetch, which often names a cuisine the primary type lacks
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Deferred

- Group voting: needs a backend and shared state; the site is static.
