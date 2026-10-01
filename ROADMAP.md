# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Rerun the Google fetch: the first run searched only 8 miles out, so the 15 to 20 minute band is thin past that, and it stopped at its call caps with 716 restaurant cells and 70 bar cells unsearched
- [ ] Before that rerun, skip grid cells whose centers are more than 20 minutes away (OSRM is free); a 12-mile grid is about 200 top-level cells against a cap of 800 calls
- [ ] Replace the seed notes with real reviews as places get visited (`visit.py`)
- [ ] Break up the "Other" cuisine (199 places Google only calls "restaurant")
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Site

- [ ] "Pick for me" button that chooses a random place from the current filters
- [ ] Price filter
- [ ] Show weekday lunch hours

## Deferred

- Group voting: needs a backend and shared state; the site is static.
