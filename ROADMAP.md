# ROADMAP.md — Development Roadmap

Open work only; completed items are removed as they land (see git history).

---

## Data

- [ ] Rerun the full fetch after 2026-11-01, when the free calls reset, to pick up the less popular places in dense spots; the runs so far stopped at their call caps with several hundred small cells unsearched, and the 20 to 23 minute band from either base has never been searched on purpose
- [ ] Replace the seed notes with real reviews as places get visited (`visit.py`)
- [ ] Bump the score for editorial recognition (D Magazine, Eater, Texas Monthly, Michelin)
- [ ] Drive times with lunch-hour traffic instead of free-flow

## Deferred

- Group voting: needs a backend and shared state; the site is static.
- Market gaps, the "simulator" proper: skipped for now by the owner (2026-10-01). Three sizes were sketched: a table of cuisine by drive-time band flagging what is absent or weak nearby; a what-if that drops a hypothetical restaurant on the map and shows its competition; and a lunch-crowd model using Census job counts by block with a choice between quality, drive time and price. A first look found no Cajun, Halal or Greek within 10 minutes and one steakhouse.
- Compressing `places.json` on the server (about 830 KB, sent uncompressed): the owner declined; it would be a homelab nginx change.
