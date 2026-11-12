# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Monthly closure check: look up every saved place by ID through Place Details, asking only for `businessStatus`, and drop or flag the closed ones. Check Google's current pricing first; that field should sit on a tier with enough free calls (about 5,000 a month) to cover every place
- [ ] Some way to pick up new openings now that coverage is essentially complete. Re-searching the grid finds them poorly: a new place rarely makes a full cell's top 20 and needs 20 reviews to be kept. Something cheaper and more targeted, such as adding a place by name, still to be worked out
- [ ] Replace the seed notes with real reviews as places get visited (`visit.py`)
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Deferred

- Group voting: needs a backend and shared state; the site is static.
- Market gaps, the "simulator" proper: skipped for now by the owner (2026-10-01). Three sizes were sketched: a table of cuisine by drive-time band flagging what is absent or weak nearby; a what-if that drops a hypothetical restaurant on the map and shows its competition; and a lunch-crowd model using Census job counts by block with a choice between quality, drive time and price. A first look found no Cajun, Halal or Greek within 10 minutes and one steakhouse.
- Compressing `places.json` on the server (about 830 KB, sent uncompressed): the owner declined; it would be a homelab nginx change.
