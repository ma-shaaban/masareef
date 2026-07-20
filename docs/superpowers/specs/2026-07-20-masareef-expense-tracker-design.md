# Masareef — expense tracker design (v1)

Date: 2026-07-20
Status: approved for implementation (owner delegated design decisions;
session note: owner asked for autonomous build, "leave the rest to your
imagination")

## Context

Masareef (مصاريف, "expenses") replaces the owner's Notion database for
tracking his and his wife's household expenses. It must stay general enough
to serve a small shop or company later. Primary usage is **adding a record
from a phone in seconds** and **viewing spend reports with charts**.

Constraints:

- Built on this repo's Nezam scaffold (FastAPI + React, one image,
  GitOps deploys). Conventions mirror the sibling `todo` app
  (`/home/mahmoud/personal/todo`), which proved them on the same platform.
- **The owner's Notion DB is live prod data: READ-ONLY, never modify.**
  Real data lands in masareef later via an export/import pass.
- Notion MCP access is currently authenticated against the wrong workspace
  (Appsilon work account) — the expenses DB is unreachable until the owner
  re-authenticates with the personal workspace. v1 therefore ships with
  representative seed data for staging; the import happens as a follow-up
  once access works.
- Installable as a PWA from Chrome on Android (and usable on iOS).

## Goals (v1)

1. Quick add: a phone-first add-expense screen — amount, category chip,
   done. Sensible defaults (today, current user, last payment method).
2. History: browse/edit/delete records, month navigation, filters.
3. Reports: monthly summary, by-category donut, daily/12-month trend
   bars, by-member split. Server-side aggregation.
4. Multi-tenant: spaces (household / shop / company) with invited members.
5. Installable PWA with app-shell offline caching.
6. Full test coverage per repo conventions (pytest + real Postgres, Vitest),
   wired into CI.

## Non-goals (v1) — explicitly deferred

- Notion importer (blocked on workspace access; design leaves room: a CSV
  import script mapping Notion export columns → transactions).
- Push notifications, offline write-queue, receipts/attachments, budgets
  and alerts, multi-currency per transaction, recurring transactions.

## Architecture

Same shape as the todo app:

- **Backend**: `APIRouter` modules in `backend/app/routers/` (auth, spaces,
  transactions, categories, reports), shared deps in `app/deps.py`
  (`CurrentUser`, `DbSession`), SQLAlchemy 2.0 ORM models in
  `app/models.py`, engine/session in `app/db.py`, security helpers
  (argon2 hashing, session cookies, login rate limiting) in
  `app/security.py`. Hand-written alembic migrations.
- **Auth**: email/password signup + login; argon2-cffi hashing; opaque
  session token in an `HttpOnly` `SameSite=Lax` cookie, SHA-256 hash stored
  server-side, 30-day rolling expiry; timing-safe login; in-memory login
  rate limiting. (Same design the todo app runs in prod.)
- **Frontend**: React 19 + react-router v8, plain CSS design tokens
  (mobile-first, dark-mode via `prefers-color-scheme`), tiny `api.js`
  fetch wrapper + `auth.jsx` context, pages in `src/pages/`, shared bits in
  `src/components/`. Charts via **Recharts**.
- **PWA**: static `public/manifest.webmanifest`, hand-rolled `public/sw.js`
  (network-first navigations, cache-first hashed assets, `/api/*`
  passthrough), 192/512/maskable/apple-touch icons, meta tags in
  `index.html`, registration in `main.jsx`. No build plugin.

## Data model

All ids UUID; all timestamps timezptz with server defaults.

- `users` — id, email (unique), password_hash, display_name, created_at.
- `sessions` — id, user_id FK cascade, token_hash (unique), expires_at,
  created_at, user_agent.
- `spaces` — id, name, kind (`household|shop|company|other`, display only),
  currency (ISO code, default `EGP`), created_by, created_at.
- `space_members` — space_id + user_id PK, role (`owner|member`),
  joined_at.
- `space_invites` — id, space_id, code (unique, URL-safe), created_by,
  created_at, revoked_at nullable. Invite link `/invite/<code>` lets a
  logged-in user join as member.
- `categories` — id, space_id, name, emoji, color (hex), sort_order,
  is_archived bool. Unique (space_id, lower(name)) among non-archived.
  Seeded per new space: Groceries 🛒, Dining 🍽️, Transport 🚗, Utilities 💡,
  Rent 🏠, Health 💊, Education 📚, Shopping 🛍️, Entertainment 🎬, Other 📦.
- `transactions` — id, space_id, type (`expense|income`, default expense),
  amount NUMERIC(14,2) > 0, occurred_on DATE, category_id FK SET NULL
  nullable, payment_method (`cash|card|wallet|bank|other`), paid_by user_id
  FK SET NULL nullable (defaults to creator), description TEXT default '',
  created_by, created_at, updated_at. Indexes: (space_id, occurred_on),
  (space_id, category_id).

Currency lives on the space (one currency per space, EGP default). Income
is a first-class type so shops can record takings; the UI defaults to
expense everywhere and offers income as a toggle.

## API surface (all `/api/*`, JSON, session cookie)

- Auth: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`,
  `GET /auth/me`, `PATCH /auth/me` (display_name).
- Spaces: `GET /spaces`, `POST /spaces`, `GET /spaces/{id}`,
  `PATCH /spaces/{id}` (name/kind/currency, owner only),
  `GET /spaces/{id}/members`, `DELETE /spaces/{id}/members/{user_id}`
  (owner removes member; anyone removes self; last owner cannot leave),
  `POST /spaces/{id}/invites` → `{code}`, `DELETE /spaces/{id}/invites/{id}`,
  `GET /invites/{code}` (preview), `POST /invites/{code}/accept`.
- Categories: `GET /spaces/{id}/categories`,
  `POST /spaces/{id}/categories`, `PATCH /categories/{id}`
  (name/emoji/color/sort_order/is_archived), `DELETE /categories/{id}`
  (only when unused, else 409 → archive instead).
- Transactions: `POST /spaces/{id}/transactions`,
  `GET /spaces/{id}/transactions?from=&to=&category_id=&paid_by=&type=&q=&limit=&offset=`
  (newest first, q searches description), `PATCH /transactions/{id}`,
  `DELETE /transactions/{id}`. Membership checked on every access; 404
  (not 403) for spaces/records the caller can't see.
- Reports (aggregation in Postgres, month params `YYYY-MM`):
  - `GET /spaces/{id}/reports/summary?month=` → totals for month
    (expense, income), previous-month expense total, per-day expense series.
  - `GET /spaces/{id}/reports/by-category?from=&to=&type=` → totals +
    percentages per category.
  - `GET /spaces/{id}/reports/by-member?from=&to=&type=` → totals per
    paid_by member.
  - `GET /spaces/{id}/reports/monthly?months=12&type=` → last N calendar
    month totals.

## Frontend screens

Routes mirror the todo app's shape (`RequireAuth` + `Layout` with bottom
tab bar on mobile):

- `/login`, `/signup`, `/invite/:code` — public.
- `/` — **Add** (the home tab: quick-add form). Big amount input
  (`inputmode=decimal`), category chip grid (emoji + name), date defaults
  today with Yesterday shortcut + date picker, payment-method segmented
  control (remembers last used per device), paid-by defaults to me,
  optional description, expense/income toggle. Submit → toast + reset,
  stays on screen for the next entry.
- `/history` — day-grouped list for the selected month, month pager,
  filter sheet (category, member, type), tap to edit in a sheet/dialog,
  delete with undo-style confirm.
- `/reports` — month pager + range presets (This month, Last month,
  Last 3 months, This year): summary cards (total spent, vs previous
  month), category donut with legend + amounts, daily bars for the month,
  12-month trend bars, by-member split.
- `/settings` — profile, current space (switcher when member of several,
  create space), members + invite link management, categories management,
  space currency/name, logout.

Space context: last-selected space id in localStorage; default = first
space. New users get a "Create your space" onboarding step (name +
kind + currency) — no auto-created space.

## Error handling

- API errors: `{"detail": str}` with correct status; frontend `ApiError`
  surfaces messages inline near the failed control; 401 anywhere →
  auth context clears and redirects to login (todo pattern).
- Amount validated > 0 and ≤ 12 digits; dates must be valid ISO;
  unknown category/member ids in filters → 422.
- DB down: API returns 503 via existing patterns; SPA shell still loads
  (SW cache) and shows a friendly retry state.

## Testing

- Backend pytest against real Postgres (docker on :5433, conftest =
  todo pattern: session-scoped `alembic upgrade head`, per-test TRUNCATE,
  TestClient with cookie jar). Cover: auth flows, membership isolation
  (user B cannot see/edit space A data — the load-bearing security tests),
  category seeding + constraints, transaction CRUD + filters, every report
  endpoint against a fixed dataset with hand-computed expected numbers.
- Frontend Vitest: api wrapper, amount/date formatting helpers, quick-add
  form logic (defaults, validation, reset after submit).
- CI: add a `test` job (Postgres service container + npm test) gating the
  image build — minimal, explained divergence in `ci.yaml` (contract file).

## Rollout

1. Feature branch → one PR with the full v1 (spec, backend, frontend, PWA,
   tests, docs). Plain-language PR body.
2. CI green → merge → CI opens staging deploy PR → auto-merge → verify
   `/api/version` == `main-<sha>` at `https://masareef-staging.nezam.site`.
3. Owner tries staging, later re-authenticates Notion (personal
   workspace); then: read real schema + sample rows (read-only), adjust
   categories/payment methods if the real data disagrees, build the CSV
   importer, and only on the owner's explicit go-ahead cut a prod release.

## Backlog (post-v1 candidates)

Notion CSV importer · push notifications (monthly summary, member added a
big expense) · offline write-queue · budgets per category with alerts ·
receipt photo attachments · recurring transactions · multi-currency ·
CSV/Excel export.
