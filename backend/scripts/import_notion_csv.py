"""Import the owner's Notion مصاريف database from Notion's own CSV export.

Usage (from backend/, with DB_* env vars pointing at the TARGET database):

    python -m scripts.import_notion_csv --csv masareef.csv \
        --email you@example.com --space "Our home" [--dry-run]

Input: Notion → ••• → Export → CSV of the expenses DB. Expected columns
(extra columns are ignored): Name, Price, Date, Tags.

Mapping — grounded in the real DB's tag audit (2,907 rows, 2026-07-20):
- The Tags multi-select mixes categories, payment cards, and modifiers.
  Category-ish tags become categories (first one wins; the rest become
  plain tags). Card tags become payment methods. Everything else (OneTime,
  SAR, unknown future tags) becomes a plain tag.
- Rows with no payment tag default to the space's "Cash" method (created
  if missing). SAR-tagged rows keep their numeric amount — the tag marks
  that the original was priced in Saudi riyal.
- Rows with an empty Price are skipped and reported. Attachments are not
  imported (receipts are a backlog feature). Future dates import as-is.

The importer only ADDS rows to masareef — it never touches Notion. It is
NOT idempotent: run it once against a freshly created space.
"""

import argparse
import csv
import datetime as dt
import sys
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import sessionmaker

from app import models
from app.db import get_engine
from app.services.tags import upsert_tags

# tag in Notion → (category name, emoji, color)
CATEGORY_TAG_MAP = {
    "Food": ("Food", "🍚", "#4f9d69"),
    "Restaurants&Cafes": ("Restaurants & Cafes", "☕", "#e07a5f"),
    "Gifts": ("Gifts", "🎁", "#e76f9b"),
    "Charity": ("Charity", "🤲", "#2a9d8f"),
    "Comex": ("Comex", "🪙", "#f2b134"),
    "Car": ("Car", "🚗", "#3d8bd4"),
    "Work": ("Work", "💼", "#8a8f98"),
    "CreditPayment": ("Credit payment", "💳", "#8d6ba8"),
}

# tag in Notion → (payment method name, icon)
PAYMENT_TAG_MAP = {
    "Credit QNB": ("Credit QNB", "💳"),
    "Credit CIB": ("Credit CIB", "💳"),
}

DEFAULT_PAYMENT_NAME = "Cash"

DATE_FORMATS = ["%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]


def parse_date(raw: str) -> dt.date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    # Notion may export a datetime like "July 16, 2026 3:04 PM" — also try
    # just the first three tokens (month, day, year) with the time dropped.
    candidates = [raw]
    tokens = raw.split(" ")
    if len(tokens) > 3:
        candidates.append(" ".join(tokens[:3]))
    for candidate in candidates:
        for fmt in DATE_FORMATS:
            try:
                return dt.datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def parse_price(raw: str) -> Decimal | None:
    raw = (raw or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        value = Decimal(raw).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _get_or_create_category(db, space_id, cache: dict, tag: str):
    name, emoji, color = CATEGORY_TAG_MAP[tag]
    key = name.lower()
    if key not in cache:
        top = (
            db.query(models.Category.sort_order)
            .filter(models.Category.space_id == space_id)
            .order_by(models.Category.sort_order.desc())
            .limit(1)
            .scalar()
        )
        c = models.Category(
            space_id=space_id, name=name, emoji=emoji, color=color, sort_order=(top or 0) + 1
        )
        db.add(c)
        db.flush()
        cache[key] = c
    return cache[key]


def _get_or_create_pm(db, space_id, cache: dict, name: str, icon: str):
    key = name.lower()
    if key not in cache:
        top = (
            db.query(models.PaymentMethod.sort_order)
            .filter(models.PaymentMethod.space_id == space_id)
            .order_by(models.PaymentMethod.sort_order.desc())
            .limit(1)
            .scalar()
        )
        p = models.PaymentMethod(
            space_id=space_id, name=name, icon=icon, sort_order=(top or 0) + 1
        )
        db.add(p)
        db.flush()
        cache[key] = p
    return cache[key]


def import_csv(db, rows, user: models.User, space: models.Space, dry_run: bool = False) -> dict:
    """rows = iterable of dicts (csv.DictReader). Returns a stats dict."""
    cat_cache = {
        c.name.lower(): c
        for c in db.query(models.Category).filter(models.Category.space_id == space.id)
    }
    pm_cache = {
        p.name.lower(): p
        for p in db.query(models.PaymentMethod).filter(models.PaymentMethod.space_id == space.id)
    }
    stats = {"imported": 0, "skipped_no_price": 0, "skipped_no_date": 0, "tagged": 0}

    for row in rows:
        price = parse_price(row.get("Price", ""))
        if price is None:
            stats["skipped_no_price"] += 1
            continue
        date = parse_date(row.get("Date", ""))
        if date is None:
            stats["skipped_no_date"] += 1
            continue
        raw_tags = [t.strip() for t in (row.get("Tags") or "").split(",") if t.strip()]

        category = None
        pm = None
        plain_tags: list[str] = []
        for tag in raw_tags:
            if tag in CATEGORY_TAG_MAP:
                if category is None:
                    category = _get_or_create_category(db, space.id, cat_cache, tag)
                else:
                    plain_tags.append(CATEGORY_TAG_MAP[tag][0])
            elif tag in PAYMENT_TAG_MAP:
                name, icon = PAYMENT_TAG_MAP[tag]
                pm = _get_or_create_pm(db, space.id, pm_cache, name, icon)
            else:
                plain_tags.append(tag)
        if pm is None:
            pm = _get_or_create_pm(db, space.id, pm_cache, DEFAULT_PAYMENT_NAME, "💵")

        tx = models.Transaction(
            space_id=space.id,
            type="expense",
            amount=price,
            occurred_on=date,
            category_id=category.id if category else None,
            payment_method_id=pm.id,
            paid_by=user.id,
            description=(row.get("Name") or "").strip(),
            created_by=user.id,
        )
        db.add(tx)
        db.flush()
        if plain_tags:
            for tag_obj in upsert_tags(db, space.id, plain_tags):
                db.add(models.TransactionTag(transaction_id=tx.id, tag_id=tag_obj.id))
            stats["tagged"] += 1
        stats["imported"] += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--email", required=True, help="owner account email in masareef")
    ap.add_argument("--space", required=True, help="target space name (must exist)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    db = SessionLocal()
    try:
        user = (
            db.query(models.User).filter(models.User.email == args.email.lower()).one_or_none()
        )
        if user is None:
            print(f"no user {args.email}", file=sys.stderr)
            return 1
        space = (
            db.query(models.Space)
            .join(models.SpaceMember, models.SpaceMember.space_id == models.Space.id)
            .filter(models.SpaceMember.user_id == user.id, models.Space.name == args.space)
            .one_or_none()
        )
        if space is None:
            print(f"no space named {args.space!r} for {args.email}", file=sys.stderr)
            return 1
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            stats = import_csv(db, csv.DictReader(f), user, space, dry_run=args.dry_run)
        print(("DRY RUN — nothing written. " if args.dry_run else "") + str(stats))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
