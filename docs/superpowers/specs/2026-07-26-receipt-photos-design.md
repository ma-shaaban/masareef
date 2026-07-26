# Masareef v1.5 — receipt photos on expenses

Date: 2026-07-26. Owner ask: attach a photo (receipt) to an expense; on
mobile open the camera; compress client-side (receipts are just numbers);
graceful web fallback. Design approved 2026-07-26.

## Storage — bytes in Postgres (dedicated table)

The platform provides only Postgres (no object store); adding one breaks
the deploy contract for a household app. Receipts are compressed hard on
the client (max ~1600px, JPEG q≈0.7 → typically 50–200 KB) and stored as
BYTEA in a dedicated `receipts` table — one row per transaction — so the
image bytes never bloat the hot `transactions` queries. Server enforces a
**2 MB** cap. One receipt per transaction (owner said "a photo"); replace
to change.

## Schema (migration 0007)

`receipts`: `id` UUID pk, `transaction_id` UUID unique FK →
transactions ON DELETE CASCADE, `mime` Text (`image/jpeg`|`image/png`|
`image/webp`), `bytes` LargeBinary (BYTEA), `size` Integer,
`created_at` timestamptz default now(). Unique on transaction_id = at most
one receipt per tx; cascade = deleting the expense removes its receipt.

## API (all member-guarded; 404 for non-members)

- `POST /api/transactions/{id}/receipt` — raw image body (content-type
  must be image/jpeg|png|webp, else 415). >2 MB → 413. Upserts (replaces an
  existing receipt for the tx). Returns `{size, mime}`.
- `GET /api/transactions/{id}/receipt` — the image bytes with its
  content-type and `Cache-Control: private, max-age=3600`. 404 if none.
  Auth via the session cookie (an `<img>` subresource carries it,
  same-origin).
- `DELETE /api/transactions/{id}/receipt` — 204 (idempotent-ish; 404 if
  none).
- Transaction JSON gains `has_receipt: bool` (subquery/exists, no bytes in
  the list payload).

## Frontend

- `src/receipt.js` — `compressImage(file) → Blob`: draw to canvas,
  downscale so the longest side ≤ 1600px, export `image/jpeg` q=0.72;
  fall back to the original file if canvas/export unavailable. Returns the
  smaller of {compressed, original}.
- `src/components/ReceiptField.jsx` — reusable control:
  - hidden `<input type="file" accept="image/*" capture="environment">`
    (camera on mobile, file picker on desktop);
  - states: none → "📷 Add receipt" button (+ hint "on your phone this
    opens the camera"); selected/existing → thumbnail (objectURL for a
    pending file, or the GET endpoint for a saved one) with "View" (opens
    full image) and "Remove"; a "Replace" affordance re-opens the picker.
  - Two modes: **deferred** (Add screen — no tx id yet: holds the compressed
    Blob, exposes it to the parent to upload after the tx is created) and
    **live** (editor — tx id exists: uploads/deletes immediately).
- `Add.jsx`: a ReceiptField (deferred). On submit, create the tx, then if a
  receipt blob is held, `POST` it to the new tx id (failure surfaces a
  non-fatal "expense saved, receipt upload failed — add it from History"
  message; the expense still saves).
- `TxEditor.jsx`: a ReceiptField (live) using the tx id; add/replace/remove
  hit the API directly.
- `History.jsx`: show a small 📎 in a row's sub-line when `has_receipt`.

## Testing

- Backend: upload → get round-trips bytes + mime; replace overwrites;
  delete → 204 then get 404; non-image body → 415; >2 MB → 413; non-member
  → 404 on all three; `has_receipt` true after upload / false after delete
  and in the list; deleting the tx cascades the receipt (get 404).
- Frontend: `compressImage` returns a Blob and never exceeds the original
  size (mock canvas in jsdom, or guard the fallback path); ReceiptField
  shows the Add button when empty and a thumbnail + Remove after selecting
  (mock compress + object URL); deferred mode exposes the blob to parent.

## Rollout

One PR → CI green → staging verify (snap a real photo on a phone) → owner
OK → prod release (v1.5.0).
