"""Core of the Notion CSV import — shared by the CLI script and the
member-only import API endpoint.

Input rows come from Notion's CSV export of the مصاريف DB (columns Name,
Price, Date, Tags; extra columns ignored). Mapping is grounded in the real
DB's tag audit (2,907 rows, 2026-07-20): card tags become payment methods;
every other tag becomes a category — known category tags first (with their
emoji/colors), then modifiers (OneTime ⭐, SAR 🇸🇦, unknown 🏷️). The first
category is the record's MAIN one. Rows with no payment tag default to
Cash; empty-price rows are skipped and counted.

Never commits — the caller decides (commit for real runs, rollback for
dry runs)."""

import datetime as dt
import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app import models

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

# modifier tags → category look; anything unknown falls back to 🏷️
MODIFIER_TAG_MAP = {
    "OneTime": ("OneTime", "⭐", "#f2b134"),
    "SAR": ("SAR", "🇸🇦", "#2a9d8f"),
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


def _get_or_create_category(db, space_id, cache: dict, spec: tuple):
    name, emoji, color = spec
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


def import_csv(
    db: Session,
    rows,
    space: models.Space,
    paid_by: uuid.UUID,
    created_by: uuid.UUID,
) -> dict:
    """rows = iterable of dicts (csv.DictReader). Adds transactions to the
    session WITHOUT committing. Returns a stats dict."""
    cat_cache = {
        c.name.lower(): c
        for c in db.query(models.Category).filter(models.Category.space_id == space.id)
    }
    pm_cache = {
        p.name.lower(): p
        for p in db.query(models.PaymentMethod).filter(models.PaymentMethod.space_id == space.id)
    }
    stats = {"imported": 0, "skipped_no_price": 0, "skipped_no_date": 0, "multi_category": 0}

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

        pm = None
        main_specs: list[tuple] = []   # known category tags, in order
        extra_specs: list[tuple] = []  # modifiers/unknown tags, in order
        for tag in raw_tags:
            if tag in CATEGORY_TAG_MAP:
                main_specs.append(CATEGORY_TAG_MAP[tag])
            elif tag in PAYMENT_TAG_MAP:
                name, icon = PAYMENT_TAG_MAP[tag]
                pm = _get_or_create_pm(db, space.id, pm_cache, name, icon)
            else:
                extra_specs.append(MODIFIER_TAG_MAP.get(tag, (tag, "🏷️", "#8a8f98")))
        if pm is None:
            pm = _get_or_create_pm(db, space.id, pm_cache, DEFAULT_PAYMENT_NAME, "💵")

        # Explicit id: lets the category links reference the row without a
        # per-row flush (matters at ~3k rows inside one request).
        tx = models.Transaction(
            id=uuid.uuid4(),
            space_id=space.id,
            type="expense",
            amount=price,
            occurred_on=date,
            payment_method_id=pm.id,
            paid_by=paid_by,
            description=(row.get("Name") or "").strip(),
            created_by=created_by,
        )
        db.add(tx)
        seen_cat_ids = set()
        position = 0
        for spec in main_specs + extra_specs:
            category = _get_or_create_category(db, space.id, cat_cache, spec)
            if category.id in seen_cat_ids:
                continue
            seen_cat_ids.add(category.id)
            db.add(
                models.TransactionCategory(
                    transaction_id=tx.id, category_id=category.id, position=position
                )
            )
            position += 1
        if position > 1:
            stats["multi_category"] += 1
        stats["imported"] += 1

    return stats
