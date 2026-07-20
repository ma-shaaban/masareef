# Masareef v1.1 — Notion data alignment

Date: 2026-07-20. Follows the v1 spec after first read access to the real
Notion DB (personal workspace re-authenticated). Notion stays READ-ONLY.

## What the real data showed (data source `66c1c644…`, 2,907 rows, 2024-03 → 2026-08)

- Dominant record shape: **Arabic free-text Name + Price + Date, no tags**
  (~83% untagged; the owner stopped tagging — exactly the friction masareef's
  category chips remove).
- `Tags` (multi-select) mixes three concepts:
  - categories: Food, Restaurants&Cafes, Gifts, Charity, Comex, Car, Work,
    CreditPayment (card bill payments)
  - payment cards: Credit QNB (139 rows), Credit CIB (124)
  - modifiers: OneTime (26 big one-offs, 2.57M total), SAR (37 rows priced
    in Saudi riyal)
- 37 rows have receipt attachments; 10 rows have null Price; a few rows are
  future-dated (planned donations).
- Expense-only: no negative prices, no income records.

## Changes

1. **Per-space payment methods** (replaces the fixed enum): table
   `payment_methods` (id, space_id, name, icon, sort_order, is_archived);
   seeded per space: Cash 💵, Card 💳, Bank 🏦, Wallet 📱. CRUD API mirrors
   categories (`/api/spaces/{id}/payment-methods`, PATCH/DELETE on
   `/api/payment-methods/{id}`, delete → 409 when in use). Transactions
   carry nullable `payment_method_id` (SET NULL); create defaults to the
   space's first active method. Migration 0005 backfills existing rows from
   the old enum values and drops the column. Add/Editor use the space list;
   Settings gains a manager card.
2. **Tags** (optional multi): `tags` (id, space_id, name, is_archived,
   unique active name per space) + `transaction_tags` m2m. Transactions
   accept `tags: [name, …]` on create/patch (names upserted per space,
   case-insensitive); responses embed `tags: [{id, name}]`.
   `GET /api/spaces/{id}/tags` lists (with usage counts). History gains a
   `tag` filter param + UI select; Add shows tag chips (existing tags +
   free entry) under a collapsed "Tags" row; editor same.
3. **Arabic-friendly text**: `dir="auto"` on description/name inputs and on
   rendered description/tag/category text so RTL renders correctly. Search
   stays ILIKE (works for Arabic).
4. **Notion CSV importer**: `backend/scripts/import_notion_csv.py` — input =
   Notion's own "Export → CSV" of the مصاريف DB (columns Name, Price, Date,
   Tags comma-separated, Attachment). Configurable mapping (defaults from
   the real tag audit):
   - categories ← Food→Food, Restaurants&Cafes, Gifts, Charity, Comex, Car,
     Work, CreditPayment (created in the target space if missing, with
     emoji/color defaults)
   - payment methods ← Credit QNB, Credit CIB (created if missing); no
     payment tag → Cash
   - plain tags ← OneTime, SAR (SAR rows keep their numeric amount; the tag
     marks the foreign-currency caveat)
   - null-Price rows skipped and reported; attachment column ignored
     (receipts = backlog); future dates imported as-is.
   Flags: `--csv path --email owner --space name [--dry-run]`. Idempotency:
   re-running duplicates — documented; run once against a fresh space
   (prod import happens on owner's go-ahead).
5. **Demo seed** updated to the new schema (payment methods per space).

Out of scope (unchanged backlog): receipts/attachments, multi-currency
amounts, income import (none exist), push notifications.

## Tests

Backend: payment-method CRUD + seeding + 409-in-use + isolation; tags
upsert/normalize/filter; transactions round-trip with new fields; migration
backfill sanity (implicitly via suite running on migrated schema); importer
unit tests on a synthetic CSV fixture (mapping, skips, dry-run). Frontend:
Add posts payment_method_id + tags. All existing suites stay green.
