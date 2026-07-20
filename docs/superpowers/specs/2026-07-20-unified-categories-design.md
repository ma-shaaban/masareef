# Masareef v1.2 — unified categories (owner decision 2026-07-20)

Owner: "I want Tags to be the same as categories" + "filter by the category
in the report". Chosen model (owner picked from two options): **one unified
system** — the separate tags concept is removed; a record carries an
ordered list of categories. The FIRST is its **main** category and drives
the by-category chart; the rest behave like labels. Also: every report can
be filtered by category.

## Data model

- New m2m `transaction_categories` (transaction_id FK CASCADE,
  category_id FK CASCADE, position int; PK (transaction_id, category_id);
  position 0 = main).
- Dropped: `tags`, `transaction_tags`, and `transactions.category_id`.
- Migration 0006 backfills: old `category_id` → position 0; each old tag →
  a same-space category (matched case-insensitively by name, created with
  emoji 🏷️ / color #8a8f98 when missing) appended in name order.

## API

- Transactions accept `category_ids: [uuid, …]` (ordered, deduped, ≤10,
  all must belong to the space; empty = uncategorized). Responses carry
  `categories: [{id,name,emoji,color}, …]` in order (main first). The old
  `category`/`tags` fields and `/spaces/{id}/tags` endpoint are removed —
  clean break, no external API consumers exist.
- Transactions list: `category_id` filter matches ANY position.
- Reports: `summary`, `by-member`, `monthly` accept optional
  `category_id` (any-position match). `by-category` groups by MAIN
  category only (each expense counted once) and also accepts the
  `category_id` filter (rows still grouped by main — useful e.g. "which
  main categories do my OneTime records fall under").

## Frontend

- One chips row (Add + editor): tap to select in order; first selected is
  marked as main (star); tap again to remove. TagPicker deleted.
- History: filter unchanged (any-match); row shows main category emoji,
  extra categories in the sub-line.
- Reports: category filter select above the cards; all sections respect
  it; donut hidden only when it would be a single slice equal to the
  filter itself (i.e. filtering by a category that is always main).
  Simpler rule implemented: donut always shown (grouped by main).
- Settings: categories manager unchanged (it already covers the unified
  concept). Payment methods untouched.

## Importer

All Notion tag names now map to categories, in this order: category-ish
tags first (Food, Restaurants&Cafes, …, per the v1.1 audit map, with their
emoji/colors), then modifiers (OneTime ⭐, SAR 🇸🇦, unknown → 🏷️). First
mapped tag = main. Payment tags (Credit QNB/CIB) unchanged → payment
methods. Untagged rows stay uncategorized.

## Tests

Updated: transactions (multi-category round-trip, ordering, any-match
filter, cross-space validation), reports (primary grouping +
category_id filter with hand-computed numbers), importer (multi-tag rows →
ordered categories), frontend Add (posts ordered category_ids). Removed:
tags tests. Payment-method suites untouched.
