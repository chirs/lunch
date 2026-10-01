# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Run the first Google fetch (`./update.py`, needs `GOOGLE_MAPS_API_KEY` in `.env`); until then the site shows the 35-place seed list with no quality scores
- [ ] Add first-hand `notes` and `my_rating` as places get visited
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Site

- [ ] "Pick for me" button that chooses a random place from the current filters
- [ ] Price filter
- [ ] Show weekday lunch hours

## Deferred

- Group voting: needs a backend and shared state; the site is static.
