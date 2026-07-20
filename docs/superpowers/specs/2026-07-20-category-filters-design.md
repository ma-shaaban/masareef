# Masareef v1.3 — multi include/exclude category filters

Owner ask (2026-07-20): History + Reports filters should allow selecting
MULTIPLE categories and EXCLUDING categories; UX delegated ("best UX but
make it simple").

## UX: tri-state chips

One horizontally-scrollable chips row (shared `CategoryFilter` component)
in History (replacing the category dropdown) and Reports (replacing the
category select). Tap cycles each chip: neutral → ✓ include → ✕ exclude
(struck through, danger tint) → neutral. A "Clear" chip appears when any
state is set. Active (non-archived) categories only.

Semantics: a record matches when it carries ANY included category (any
position) AND NONE of the excluded ones. With no includes, everything
except excluded matches (uncategorized records naturally survive
excludes).

## API

`category_id` (single) is replaced on the transactions list and all four
report endpoints by repeatable query params:

- `category_ids=<uuid>&category_ids=<uuid>…` — include, any-of
- `exclude_category_ids=<uuid>…` — exclude, none-of

Every id must belong to the space (422 otherwise). `by-category` still
groups matching records by MAIN category. Clean break (no consumers).

## Tests

Backend: include-OR across two categories; exclude keeps uncategorized;
include+exclude combined; foreign id in either list → 422; report numbers
hand-computed on the existing dataset. Frontend: CategoryFilter cycling
component test (include → exclude → clear payloads).
