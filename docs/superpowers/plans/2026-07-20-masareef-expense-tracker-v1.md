# Masareef Expense Tracker v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship masareef v1 — multi-tenant expense tracker PWA (quick mobile add, history, chart reports) — to staging via one PR.

**Architecture:** Mirror the proven sibling app `/home/mahmoud/personal/todo`: FastAPI routers + SQLAlchemy 2.0 ORM + hand-written alembic migrations + argon2/cookie-session auth on the backend; React 19 + react-router 8 + plain-CSS design tokens + Recharts on the frontend; hand-rolled service worker for PWA. Spec: `docs/superpowers/specs/2026-07-20-masareef-expense-tracker-design.md`.

**Tech Stack:** FastAPI 0.139, SQLAlchemy 2.0.51, alembic, psycopg 3, argon2-cffi, pytest; React 19, Vite 8, react-router ^8, recharts ^3, vitest ^4.

**Reference implementation:** the todo app at `/home/mahmoud/personal/todo` — when a task says "todo pattern", open the named file there and adapt (rename todo→masareef, drop push/reminders). NEVER copy todo-specific business logic.

**Environment facts:** masareef repo = `/home/mahmoud/personal/masareef`, branch `feat/expense-tracker-v1`. Local test Postgres for masareef: port **5434** (todo already owns 5433), container `masareef-test-pg`, user/db `masareef`/`masareef_test`, password `test`. Git commits: use `--no-gpg-sign` (GPG prompts hang in this harness). Staging URL: `https://masareef-staging.nezam.site`.

---

### Task 0: Dev environment

**Files:** none (environment only)

- [ ] Start test Postgres: `docker run -d --name masareef-test-pg -p 5434:5432 -e POSTGRES_USER=masareef -e POSTGRES_PASSWORD=test -e POSTGRES_DB=masareef_test postgres:16-alpine` (if name conflict: `docker start masareef-test-pg`)
- [ ] Create `backend/requirements-dev.txt`: `pytest==8.*`, `httpx` (TestClient dep). Runtime deps to ADD to `backend/requirements.txt`: `argon2-cffi==25.1.0` (verify latest on PyPI at execution).
- [ ] Venv: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r backend/requirements.txt -r backend/requirements-dev.txt`
- [ ] Frontend deps: `cd frontend && npm install && npm install react-router recharts && npm install -D vitest @testing-library/react jsdom`
- [ ] Sanity: `.venv/bin/python -c "import fastapi, argon2"` and `cd frontend && npx vitest --version`
- [ ] Commit lockfile/requirements changes: `git add -A && git commit --no-gpg-sign -m "chore: dev deps for backend tests and frontend router/charts/tests"`

### Task 1: Backend foundation — db, models (users/sessions), security, deps

**Files:**
- Create: `backend/app/db.py` — engine from `DB_*` env vars (todo pattern: `/home/mahmoud/personal/todo/backend/app/db.py`), `Base(DeclarativeBase)`, `get_db()` yielding a session that commits on success / rolls back on exception.
- Create: `backend/app/models.py` — `User` (id UUID pk default uuid4, email Text unique index, password_hash Text, display_name Text, created_at timestamptz server_default now()), `UserSession` (id, user_id FK CASCADE, token_hash Text unique, expires_at, created_at, user_agent Text default '').
- Create: `backend/app/security.py` — todo pattern (`/home/mahmoud/personal/todo/backend/app/security.py`): argon2 `PasswordHasher(time_cost=2, memory_cost=19*1024, parallelism=1)` behind a `threading.Semaphore(4)`; `hash_password`/`verify_password` (verify hashes a dummy on unknown email for timing safety); `new_session_token()` = `secrets.token_urlsafe(32)`, stored as sha256 hexdigest; `set_session_cookie(response, token)` HttpOnly SameSite=Lax max_age 30d, `secure=` from env `COOKIE_SECURE` default true off localhost — follow todo's exact approach; rolling refresh when < 15 days left; in-memory login rate limiter (15-min window: 10 fails/email+ip, 30/email) with `reset_rate_limit()` for tests.
- Create: `backend/app/deps.py` — `DbSession = Annotated[Session, Depends(get_db)]`; `CurrentUser` dependency: read `session` cookie → sha256 → lookup unexpired UserSession → refresh if rolling window hit → return User; else 401.
- Create: `backend/alembic/versions/0002_auth_tables.py` — users + sessions tables + unique indexes (todo's 0002 shape).
- Create: `backend/tests/conftest.py` — todo pattern: env defaults host localhost port **5434** user masareef pw test db masareef_test; session fixture runs `alembic upgrade head`; `client` = TestClient(app); autouse `clean_tables` truncates all tables except `alembic_version` CASCADE after each test.
- Test: `backend/tests/test_smoke.py`

- [ ] Write `backend/tests/test_smoke.py`: `test_healthz` (200, `{"status":"ok"}`), `test_db_check_ok` (200 against test DB — set `DB_PORT`=5434 etc. in conftest env before importing app), `test_unknown_api_is_json_404`.
- [ ] Run `cd backend && ../.venv/bin/python -m pytest -q` → fails (no conftest yet). Implement conftest + db.py; ensure conftest sets `DB_HOST/PORT/NAME/USER/PASSWORD` env to the test DB **before** `from app.main import app` so `_db_conninfo()` and the engine both hit it.
- [ ] Implement models.py, security.py, deps.py, migration 0002. Run pytest → smoke green.
- [ ] Commit: `git add -A && git commit --no-gpg-sign -m "feat: backend foundation (db, models, security, deps, auth tables)"`

### Task 2: Auth router + tests

**Files:**
- Create: `backend/app/routers/__init__.py`, `backend/app/routers/auth.py` — `APIRouter(prefix="/api/auth")`: `POST /signup` {email, password≥8, display_name} → 201 user json + session cookie (409 duplicate email, case-insensitive); `POST /login` (401 same detail for bad pw / unknown email; rate limited → 429); `POST /logout` (delete session row + clear cookie); `GET /me`; `PATCH /me` {display_name}.
- Modify: `backend/app/main.py` — `app.include_router(auth.router)` above SPA catch-all.
- Test: `backend/tests/test_auth.py` (todo's test_auth.py shape + `reset_rate_limit` autouse fixture)

- [ ] Write tests first: signup sets cookie & /me works; duplicate email 409; login ok; wrong-password vs unknown-email identical 401 body; logout clears (me → 401); patch display_name; short password 422.
- [ ] Run → fail. Implement router, wire into main.py. Run → pass.
- [ ] Commit `feat: auth (signup/login/logout/me) with cookie sessions`

### Task 3: Spaces, members, invites, categories schema + seed

**Files:**
- Modify: `backend/app/models.py` — add `Space` (id, name, kind Text default 'household', currency Text default 'EGP', created_by FK SET NULL, created_at), `SpaceMember` (space_id+user_id composite pk, role Text default 'member', joined_at), `SpaceInvite` (id, space_id FK CASCADE, code Text unique, created_by, created_at, revoked_at nullable), `Category` (id, space_id FK CASCADE, name Text, emoji Text default '', color Text default '', sort_order Int default 0, is_archived Bool default false).
- Create: `backend/alembic/versions/0003_spaces_categories.py` — the four tables; unique index `ix_categories_space_lower_name` on (space_id, lower(name)) WHERE NOT is_archived (partial, via `sa.text`).
- Create: `backend/app/services/__init__.py`, `backend/app/services/seeds.py` — `DEFAULT_CATEGORIES = [("Groceries","🛒","#4f9d69"), ("Dining","🍽️","#e07a5f"), ("Transport","🚗","#3d8bd4"), ("Utilities","💡","#f2b134"), ("Rent","🏠","#8d6ba8"), ("Health","💊","#d64550"), ("Education","📚","#2a9d8f"), ("Shopping","🛍️","#e76f9b"), ("Entertainment","🎬","#f4845f"), ("Other","📦","#8a8f98")]`; `seed_categories(db, space_id)`.
- Create: `backend/app/routers/spaces.py` — endpoints per spec §API: spaces CRUD-ish, members list/remove (owner removes anyone; member removes self; blocking removal of last owner), invites create/revoke, `GET /api/invites/{code}` preview (space name + member count, 404 if revoked/unknown), `POST /api/invites/{code}/accept` (idempotent when already member). Membership guard helper `get_space_or_404(db, space_id, user)` — returns 404 (not 403) for non-members. Space create → creator becomes owner + categories seeded.
- Modify: `backend/app/main.py` — include router.
- Test: `backend/tests/test_spaces.py`

- [ ] Tests first: create space seeds 10 categories + owner membership; GET /spaces lists only mine; non-member gets 404 on foreign space (the isolation test); invite accept adds member; revoked invite 404; member self-leave ok; last owner cannot leave (409); owner PATCH currency; member PATCH → 403.
- [ ] Run → fail. Implement migration + models + router. Run → pass.
- [ ] Commit `feat: spaces, membership, invites, seeded categories`

### Task 4: Categories router

**Files:**
- Create: `backend/app/routers/categories.py` — `GET /api/spaces/{id}/categories` (ordered sort_order, name; `?include_archived=1` to include archived), `POST /api/spaces/{id}/categories` (409 duplicate active name case-insensitive), `PATCH /api/categories/{id}` (name/emoji/color/sort_order/is_archived), `DELETE /api/categories/{id}` — 409 with `{"detail": "in use; archive instead"}` when transactions reference it, else delete.
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_categories.py`

- [ ] Tests first: list seeded; create custom; duplicate name 409; archive hides from default list; delete unused ok; **delete in-use → 409** (needs a transaction — write this specific test in Task 5 instead if transactions don't exist yet: keep a placeholder-free note → move that single case to test_transactions.py); non-member 404.
- [ ] Implement, pass, commit `feat: category management`.

### Task 5: Transactions

**Files:**
- Modify: `backend/app/models.py` — `Transaction` (id, space_id FK CASCADE, type Text default 'expense' CHECK in ('expense','income'), amount Numeric(14,2) CHECK > 0, occurred_on Date, category_id FK SET NULL nullable, payment_method Text default 'cash' CHECK in ('cash','card','wallet','bank','other'), paid_by FK SET NULL nullable, description Text default '', created_by FK SET NULL, created_at, updated_at server_default now() onupdate now()). Indexes (space_id, occurred_on), (space_id, category_id).
- Create: `backend/alembic/versions/0004_transactions.py`
- Create: `backend/app/routers/transactions.py` —
  `POST /api/spaces/{id}/transactions` {amount, occurred_on?=today, type?, category_id?, payment_method?, paid_by?=caller, description?} — validate category belongs to space (422), paid_by is a member (422);
  `GET /api/spaces/{id}/transactions` filters `from,to,category_id,paid_by,type,q,limit<=200 default 50,offset` ordered occurred_on DESC, created_at DESC, returns `{"items":[...],"total":N}`; item embeds category name/emoji + paid_by display_name (joined, no N+1: single query with outer joins);
  `PATCH /api/transactions/{id}` same validations; `DELETE /api/transactions/{id}`. Access via record→space membership, 404 otherwise.
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_transactions.py`

- [ ] Tests first: create minimal (amount only → today, expense, cash, paid_by=me); full create; amount 0 / negative → 422; foreign category → 422; list newest-first with total; each filter (from/to, category, paid_by, type, q substring on description); pagination; patch amount+category; delete; **cross-space isolation** (B cannot GET/PATCH/DELETE A's transaction → 404); category delete in-use → 409 (the case deferred from Task 4).
- [ ] Implement, pass, commit `feat: transactions CRUD with filters`.

### Task 6: Reports

**Files:**
- Create: `backend/app/routers/reports.py` — all under `/api/spaces/{id}/reports/`, expense-only unless `type` given, SQL aggregation:
  - `summary?month=YYYY-MM` → `{"month","expense_total","income_total","prev_expense_total","daily":[{"date","total"}...]}` (daily only days with data; totals as strings of Decimal quantized .01 — Pydantic serializes Decimal→str? **Decide: serialize all money as float via `float(x)`** — amounts ≤ 12 digits so float is exact enough for display; document in docstring).
  - `by-category?from&to&type` → `[{"category_id","name","emoji","color","total","count","pct"}]` desc by total, uncategorized as `category_id: null, name: "Uncategorized"`; pct rounded 1 decimal of range total.
  - `by-member?from&to&type` → `[{"user_id","display_name","total","count"}]` (paid_by NULL → "Unassigned").
  - `monthly?months=12&type` → last N calendar months ending current month, zero-filled: `[{"month":"YYYY-MM","total"}]` — generate the month list in Python, LEFT-join totals from `date_trunc('month', occurred_on)` GROUP BY.
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_reports.py`

- [ ] Tests first against one fixed dataset (helper builds: space with 2 members, categories, ~10 transactions across 3 months incl. one income, one uncategorized, one paid by member 2) with hand-computed expected numbers for all four endpoints; month param validation (`2026-13` → 422); non-member 404.
- [ ] Implement, pass, commit `feat: report aggregation endpoints`.

### Task 7: Demo seed script

**Files:**
- Create: `backend/scripts/seed_demo.py` — idempotent-ish (skips if user exists): demo user `demo@masareef.local` / `demo1234`, space "Demo Household" EGP, ~180 transactions over 6 months (random-ish but deterministic via `random.Random(42)`; realistic EGP amounts per category; a few incomes; both members? single demo user is fine). Run: `cd backend && ../.venv/bin/python -m scripts.seed_demo` (needs `scripts/__init__.py`). Uses same env vars as app.
- [ ] Run against test DB (`DB_PORT=5434 DB_USER=masareef DB_PASSWORD=test DB_NAME=masareef_test ...`), verify via a quick psql count, commit `feat: demo data seed script`.

### Task 8: Frontend foundation — tokens, api, auth, router, layout, auth pages

**Files:**
- Create: `frontend/src/styles.css` — design tokens (todo pattern `/home/mahmoud/personal/todo/frontend/src/styles.css`): CSS vars (bg, card, text, muted, accent `#0e9f6e` money-green, danger, radii, spacing), dark via `prefers-color-scheme`, `.topbar`, `.tabbar` fixed bottom w/ `env(safe-area-inset-bottom)`, max-width 640px shell, buttons/inputs/chips/cards utilities.
- Create: `frontend/src/api.js` — todo pattern: `api(path, {method, body})`, JSON, `ApiError{status,message}`, emits `authEvents` 'logout' on 401.
- Create: `frontend/src/auth.jsx` — `AuthProvider` (me on mount), `useAuth`, `RequireAuth` redirect `/login?next=`.
- Create: `frontend/src/format.js` — `fmtMoney(n, currency)` via `Intl.NumberFormat('en-EG',{style:'currency',currency})` w/ graceful fallback; `fmtDay(iso)` ("Today"/"Yesterday"/localized d MMM); `monthLabel("YYYY-MM")`; `todayISO()`, `addMonths(ym, n)`.
- Create: `frontend/src/spaces.jsx` — `SpaceProvider`: loads `/api/spaces`, current space id from localStorage `masareef.space` (fallback first), `useSpace()` → {space, spaces, setSpaceId, refresh}. Renders onboarding `<CreateSpace/>` when zero spaces.
- Create: `frontend/src/pages/Login.jsx`, `Signup.jsx`, `CreateSpace.jsx` (name, kind select, currency select [EGP, USD, EUR, SAR, AED, GBP] default EGP).
- Create: `frontend/src/components/Layout.jsx` — topbar (app name + space name), `<Outlet/>`, bottom tabbar: ➕ Add `/`, 🧾 History `/history`, 📊 Reports `/reports`, ⚙️ Settings `/settings`.
- Rewrite: `frontend/src/App.jsx` — BrowserRouter/AuthProvider/SpaceProvider + routes per spec; `frontend/src/main.jsx` — import styles.css.
- Modify: `frontend/package.json` — scripts `"test": "vitest"`.
- Create: `frontend/vitest.config.js` (jsdom env for component tests; plain js tests fine without) — or add `test` block in vite.config.js (**do that instead**, no new file).
- Test: `frontend/src/__tests__/api.test.js`, `frontend/src/__tests__/format.test.js`

- [ ] Tests first (api: ok json, ApiError detail, 401 emits logout; format: money EGP, fmtDay today/yesterday, addMonths year rollover). `npm run test -- --run` → fail → implement api.js/format.js → pass.
- [ ] Build the rest of the foundation files; `npm run build` must succeed; manual smoke via `npm run dev` + uvicorn (signup → onboarding → empty Add page renders).
- [ ] Commit `feat: frontend foundation (auth, spaces context, layout, tokens)`.

### Task 9: Quick-add page

**Files:**
- Create: `frontend/src/pages/Add.jsx` + `frontend/src/components/CategoryChips.jsx`
- Test: `frontend/src/__tests__/add.test.jsx` (jsdom + @testing-library/react)

Form state: amount (text, `inputmode="decimal"`, autofocus, big 2.5rem font), type toggle (Expense default / Income), category chips (active categories, sorted; selected highlighted; none = uncategorized), date row: chips [Today] [Yesterday] [📅 native `<input type=date>`], payment segmented (💵 Cash default→ last used from localStorage `masareef.pm`), paid-by select (space members, default me), description input. Submit disabled unless amount parses > 0. POST → success toast "Saved ✓", reset amount+description only (keep category/date/pm), refocus amount.

- [ ] Component test first: renders chips from mocked fetch, submit posts correct body, resets amount. → fail → implement → pass.
- [ ] `npm run build` green. Commit `feat: quick-add screen`.

### Task 10: History page

**Files:**
- Create: `frontend/src/pages/History.jsx`, `frontend/src/components/TxRow.jsx`, `frontend/src/components/TxEditor.jsx` (modal sheet reused for edit)

Month pager (‹ month ›), fetch `/transactions?from=&to=` for month, group client-side by occurred_on (day headers with day total), row: emoji, description||category name, member + payment small print, amount right-aligned (income green `+`), tap → TxEditor (same fields as Add, PATCH/DELETE with confirm), filter sheet: category select, member select, type select — applied as query params. Empty state message. "Load more" when total > items.length (offset paging).

- [ ] Implement (no component test — covered by build + API tests; format helpers already tested). `npm run build`. Commit `feat: history screen with month nav, filters, edit/delete`.

### Task 11: Reports page

**Files:**
- Create: `frontend/src/pages/Reports.jsx`, `frontend/src/components/charts/CategoryDonut.jsx`, `DailyBars.jsx`, `TrendBars.jsx`, `MemberSplit.jsx` (Recharts: PieChart, BarChart, ResponsiveContainer)

Range presets segmented: This month (default) / Last month / Last 3 months / This year → computes from/to; month pager visible for the month presets. Sections: summary cards (Spent, vs prev month ±% colored, Income if > 0); CategoryDonut (by-category, top 8 + Other bucket client-side, legend with amounts+pct); DailyBars (summary.daily, x=day number); TrendBars (monthly 12, x=MMM); MemberSplit (horizontal bars by-member). All money via fmtMoney. Loading skeletons + empty state.

- [ ] Implement; `npm run build`; visual smoke on seeded demo data via dev servers. Commit `feat: reports screen with charts`.

### Task 12: Settings page

**Files:**
- Create: `frontend/src/pages/Settings.jsx`, `frontend/src/pages/Invite.jsx`, `frontend/src/components/CategoryManager.jsx`

Sections: Profile (display name inline edit); Space (name/kind/currency edit for owner; switcher list + "New space" → CreateSpace flow); Members (list w/ role; owner: remove; self: leave); Invite (create link → copy `location.origin + /invite/<code>`, revoke); Categories (CategoryManager: list w/ archive toggle, add form emoji+name+color, edit inline, delete w/ 409 → offer archive); Logout. `Invite.jsx`: preview space name, Accept button → joins + redirects home.

- [ ] Implement; `npm run build`; smoke: invite second user in dev. Commit `feat: settings, members, invites, category management`.

### Task 13: PWA

**Files:**
- Create: `frontend/public/manifest.webmanifest` (name "Masareef", short_name "Masareef", start_url "/", display standalone, theme `#0e9f6e`, background `#111418`, icons 192/512/maskable-512)
- Create: `frontend/public/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png` — generate: write `scripts/gen-icons.py` (repo root scripts/) drawing a rounded-square money-note glyph "م" or "﷼"-free simple design with Pillow **if available**, else ImageMagick `magick`; keep the generator committed.
- Create: `frontend/public/sw.js` — todo's sw.js (`/home/mahmoud/personal/todo/frontend/public/sw.js`) minus push/notification handlers: cache `masareef-shell-v1`, install caches `/` + skipWaiting, activate cleans old caches + clients.claim, fetch: skip non-GET + `/api/` + `/healthz`; navigations network-first (cache fallback `/`); `/assets/`+`/icons/` cache-first.
- Modify: `frontend/index.html` — title Masareef, `<html lang="en">`, viewport `viewport-fit=cover`, theme-color, manifest link, icons, apple-mobile-web-app tags.
- Modify: `frontend/src/main.jsx` — SW registration (prod only: `if (import.meta.env.PROD && 'serviceWorker' in navigator)`).

- [ ] `npm run build` then verify `dist/` contains manifest, sw.js, icons; `docker build -t masareef-local .` and `docker run -p 8090:8080` → curl `/manifest.webmanifest`, `/sw.js`, `/icons/icon-192.png` all 200 with right content-type; Lighthouse-style manual check of manifest fields.
- [ ] Commit `feat: PWA (manifest, icons, service worker)`.

### Task 14: CI test job + docs

**Files:**
- Modify: `.github/workflows/ci.yaml` — add `test` job before/gating image build: Postgres 16 service (user masareef/pw test/db masareef_test, port 5432 mapped), steps: setup-python 3.12 + pip install -r requirements.txt -r requirements-dev.txt + `pytest -q` with TEST_DB_* env pointing at service; setup-node 24 + `npm ci` + `npm run test -- --run` + `npm run build`. `needs: test` on the build job. **Contract file — keep diff minimal; PR body must carry the divergence note.**
- Modify: `AGENTS.md` — update "Current API routes" section (routers list), tests section (they now exist + how to run, port 5434), conventions unchanged.
- Modify: `docs/index.md`, `docs/using-your-app.md` — plain-language: what masareef does, how to install on the phone (Chrome → Install app), staging/prod URLs.
- Modify: `README.md` — one-paragraph app description + local dev incl. test Postgres command.

- [ ] Update conftest to read `TEST_DB_*` first then fall back to 5434 defaults (todo pattern) so CI's service (5432) and local (5434) both work.
- [ ] Full local gate: backend pytest all green; `npm run test -- --run`; `npm run build`; `docker build`.
- [ ] Commit `chore: CI test gate + docs refresh`.

### Task 15: PR → staging

- [ ] Push branch; `gh pr create` — title `feat: masareef expense tracker v1`; body: plain-language feature list, screenshots skipped, divergence note for `ci.yaml` (test gate added), Notion import deferred note, test counts. Footer: 🤖 Generated with [Claude Code](https://claude.com/claude-code) + session link.
- [ ] Watch CI: `gh pr checks --watch`. Red → fix in-branch, never weaken tests.
- [ ] Merge (squash) when green. Then watch the staging-deploy PR: CI opens it bumping `deploy/staging/kustomization.yaml`; if repo requires human approval it'll sit — attempt auto/self-merge since main is unprotected; if blocked, hand to owner in final report.
- [ ] Verify: poll `https://masareef-staging.nezam.site/api/version` == `main-<merge shortsha>` (allow ~3-4 min; if no ci run for merge sha: `gh workflow run ci.yaml --ref main`). Then smoke: signup, create space, add expense, reports respond.
- [ ] **STOP: no prod release** — owner must verify staging first (AGENTS.md rule).

## Self-review notes

- Spec coverage: auth ✓(T1-2) spaces/invites ✓(T3) categories ✓(T4) transactions ✓(T5) reports ✓(T6) seed ✓(T7) screens ✓(T8-12) PWA ✓(T13) CI+docs ✓(T14) rollout ✓(T15). Notion importer: deferred by spec (non-goal).
- Money serialization decided: floats at the API boundary (display app; DB keeps Numeric).
- Category delete-in-use test placed in T5 (needs transactions) — noted in both tasks.
