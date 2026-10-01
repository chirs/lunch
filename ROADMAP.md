# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Finish discovery in the dense spots: the first run stopped at its call caps with 716 restaurant cells and 70 bar cells unsearched
- [ ] Skip grid cells whose centers are more than 15 minutes away (OSRM is free) so the Google calls go where they count; 882 of 3,425 places found were outside the search area
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
