# Masareef v1.4 — persistent, searchable category filter

Date: 2026-07-26. Owner asks: (1) category filters should persist when moving
between History and Reports (and survive reload); (2) selecting categories
should be easier than the horizontal-scroll chip row (owner has ~20
categories, dislikes horizontal scrolling and hunting). Chosen picker (owner
decision): a Filter button that opens a search + vertical-list bottom sheet.

## Shared filter state

New `frontend/src/filters.jsx` — `FilterProvider` + `useCategoryFilter()`
mounted UNDER `SpaceProvider` (needs the current space id). State shape:
`{ include: string[], exclude: string[] }` (category ids). Persisted to
`localStorage` key `masareef.filter.<spaceId>` (JSON). On space change, load
that space's stored filter (empty if none) — per-space isolation.

Hook API: `{ include, exclude, setFilter(include, exclude), clear() }`.
History and Reports consume this instead of local `useState`.

Stale-id healing: a stored id may reference a since-deleted/archived
category → the API 422s on unknown ids. Each consumer, once its category
list has loaded, computes `validInclude = include ∩ existingIds` (same for
exclude) and, if it differs from stored, calls `setFilter` with the pruned
lists (self-heal). Requests only ever send valid ids.

## CategoryFilterSheet component

New `frontend/src/components/CategoryFilterSheet.jsx`, replacing
`CategoryFilter.jsx` (deleted). Props: `categories` (active, non-archived),
`include`, `exclude`, `onChange(include, exclude)`.

- Collapsed: a full-width button `🔎 Filter` + ` · N active` when
  `N = include.length + exclude.length > 0`, with a `▾`.
- Open: bottom sheet (reuse `.sheet-backdrop`/`.sheet`) containing:
  - header row: "Filter by category" + a "Clear" link (disabled when N=0);
  - a search `<input dir="auto">` filtering the list by
    `name.toLowerCase().includes(query.toLowerCase())`;
  - a scrollable vertical list; each row is a button showing the state
    marker (✓ include / ✕ exclude / none), emoji, name (`dir="auto"`).
    Tap cycles neutral → include → exclude → neutral (reuse the current
    tri-state cycle logic). Included rows tinted accent; excluded rows
    tinted danger + strikethrough;
  - a sticky "Done" button closing the sheet.
- Closing (Done, backdrop tap) just hides the sheet; selections apply live
  via `onChange` as they're tapped (no separate apply step).

## Screens

`History.jsx` + `Reports.jsx`: drop local `catInclude`/`catExclude`
`useState`; read `include`/`exclude` from `useCategoryFilter()`; render
`<CategoryFilterSheet>` in place of `<CategoryFilter>`; prune stale ids as
above. History's paid_by / type / q filters stay local (unchanged) — only
the category filter is shared/persisted.

## CSS

`styles.css`: `.filter-btn` (full-width, bordered, badge), sheet list rows
(`.filter-row` with `.in`/`.out` states reusing accent/danger tints), and
the sheet search input. Remove the now-unused `.chips.scroll` /
`.chips button.exclude` / `.chips button.clear` rules if nothing else uses
them (CategoryChips still uses `.chips` + `.active`, so keep those).

## Testing

- `frontend/src/__tests__/categoryfiltersheet.test.jsx`: opens on button
  click; typing in search narrows the list; tapping a row cycles
  include→exclude→clear (asserts `onChange` payloads); active-count badge;
  Clear resets.
- `frontend/src/__tests__/filters.test.jsx`: `FilterProvider` round-trips
  through localStorage and isolates by space id (render with space A, set
  filter, switch to space B → empty, back to A → restored).
- No backend changes; all existing suites stay green.

## Rollout

One PR → CI green → staging verify → owner OK → prod release (v1.4.0).
