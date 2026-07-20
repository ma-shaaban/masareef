"""Aggregation endpoints for the reports screen. All money aggregation runs
in Postgres; amounts serialize as floats at the API boundary (display app).

Category semantics: each record has an ordered category list. The
by-category breakdown groups by the MAIN category (position 0) so every
expense is counted exactly once; the optional `category_id` filter on all
endpoints matches ANY position (a record labelled Comex+OneTime shows up
when filtering by either)."""

import datetime as dt
import re
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Date, and_, cast, func

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership
from app.routers.transactions import TYPES, apply_category_filters

router = APIRouter(prefix="/api", tags=["reports"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _parse_month(value: str) -> tuple[dt.date, dt.date]:
    """'YYYY-MM' → (first day, last day) of that month."""
    if not _MONTH_RE.match(value):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    year, month = int(value[:4]), int(value[5:7])
    first = dt.date(year, month, 1)
    last = (first + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    return first, last


def _prev_month(first: dt.date) -> tuple[dt.date, dt.date]:
    prev_last = first - dt.timedelta(days=1)
    return prev_last.replace(day=1), prev_last


def _validate_type(type_: str) -> str:
    if type_ not in TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(TYPES)}")
    return type_


def _range_total(db, space_id, first, last, type_, include_ids, exclude_ids) -> float:
    q = db.query(func.coalesce(func.sum(models.Transaction.amount), 0)).filter(
        models.Transaction.space_id == space_id,
        models.Transaction.type == type_,
        models.Transaction.occurred_on >= first,
        models.Transaction.occurred_on <= last,
    )
    q = apply_category_filters(db, q, space_id, include_ids, exclude_ids)
    return float(q.scalar())


@router.get("/spaces/{space_id}/reports/summary")
def summary(
    space_id: uuid.UUID,
    month: str,
    user: CurrentUser,
    db: DbSession,
    category_ids: list[uuid.UUID] = Query(default=[]),
    exclude_category_ids: list[uuid.UUID] = Query(default=[]),
):
    get_membership(db, space_id, user)
    first, last = _parse_month(month)
    prev_first, prev_last = _prev_month(first)
    daily_q = (
        db.query(
            models.Transaction.occurred_on,
            func.sum(models.Transaction.amount),
        )
        .filter(
            models.Transaction.space_id == space_id,
            models.Transaction.type == "expense",
            models.Transaction.occurred_on >= first,
            models.Transaction.occurred_on <= last,
        )
    )
    daily_q = apply_category_filters(db, daily_q, space_id, category_ids, exclude_category_ids)
    daily_rows = daily_q.group_by(models.Transaction.occurred_on).order_by(
        models.Transaction.occurred_on
    ).all()
    return {
        "month": month,
        "expense_total": _range_total(
            db, space_id, first, last, "expense", category_ids, exclude_category_ids
        ),
        "income_total": _range_total(
            db, space_id, first, last, "income", category_ids, exclude_category_ids
        ),
        "prev_expense_total": _range_total(
            db, space_id, prev_first, prev_last, "expense", category_ids, exclude_category_ids
        ),
        "daily": [{"date": d.isoformat(), "total": float(t)} for d, t in daily_rows],
    }


@router.get("/spaces/{space_id}/reports/by-category")
def by_category(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_: dt.date | None = Query(default=None, alias="from"),
    to: dt.date | None = None,
    type: str = "expense",
    category_ids: list[uuid.UUID] = Query(default=[]),
    exclude_category_ids: list[uuid.UUID] = Query(default=[]),
):
    get_membership(db, space_id, user)
    _validate_type(type)
    # Group by the MAIN category: join only the position-0 row.
    q = (
        db.query(
            models.Category.id,
            models.Category.name,
            models.Category.emoji,
            models.Category.color,
            func.sum(models.Transaction.amount).label("total"),
            func.count(models.Transaction.id).label("count"),
        )
        .select_from(models.Transaction)
        .outerjoin(
            models.TransactionCategory,
            and_(
                models.TransactionCategory.transaction_id == models.Transaction.id,
                models.TransactionCategory.position == 0,
            ),
        )
        .outerjoin(models.Category, models.Category.id == models.TransactionCategory.category_id)
        .filter(models.Transaction.space_id == space_id, models.Transaction.type == type)
    )
    if from_ is not None:
        q = q.filter(models.Transaction.occurred_on >= from_)
    if to is not None:
        q = q.filter(models.Transaction.occurred_on <= to)
    q = apply_category_filters(db, q, space_id, category_ids, exclude_category_ids)
    rows = (
        q.group_by(
            models.Category.id, models.Category.name, models.Category.emoji, models.Category.color
        )
        .order_by(func.sum(models.Transaction.amount).desc())
        .all()
    )
    grand = sum(float(r.total) for r in rows)
    return [
        {
            "category_id": str(r.id) if r.id else None,
            "name": r.name if r.id else "Uncategorized",
            "emoji": r.emoji if r.id else "❔",
            "color": r.color if r.id else "#8a8f98",
            "total": float(r.total),
            "count": r.count,
            "pct": round(float(r.total) / grand * 100, 1) if grand else 0.0,
        }
        for r in rows
    ]


@router.get("/spaces/{space_id}/reports/by-member")
def by_member(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_: dt.date | None = Query(default=None, alias="from"),
    to: dt.date | None = None,
    type: str = "expense",
    category_ids: list[uuid.UUID] = Query(default=[]),
    exclude_category_ids: list[uuid.UUID] = Query(default=[]),
):
    get_membership(db, space_id, user)
    _validate_type(type)
    q = (
        db.query(
            models.User.id,
            models.User.display_name,
            func.sum(models.Transaction.amount).label("total"),
            func.count(models.Transaction.id).label("count"),
        )
        .select_from(models.Transaction)
        .outerjoin(models.User, models.User.id == models.Transaction.paid_by)
        .filter(models.Transaction.space_id == space_id, models.Transaction.type == type)
    )
    if from_ is not None:
        q = q.filter(models.Transaction.occurred_on >= from_)
    if to is not None:
        q = q.filter(models.Transaction.occurred_on <= to)
    q = apply_category_filters(db, q, space_id, category_ids, exclude_category_ids)
    rows = (
        q.group_by(models.User.id, models.User.display_name)
        .order_by(func.sum(models.Transaction.amount).desc())
        .all()
    )
    return [
        {
            "user_id": str(r.id) if r.id else None,
            "display_name": r.display_name if r.id else "Unassigned",
            "total": float(r.total),
            "count": r.count,
        }
        for r in rows
    ]


@router.get("/spaces/{space_id}/reports/monthly")
def monthly(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    months: int = Query(default=12, ge=1, le=36),
    end: str | None = None,
    type: str = "expense",
    category_ids: list[uuid.UUID] = Query(default=[]),
    exclude_category_ids: list[uuid.UUID] = Query(default=[]),
):
    get_membership(db, space_id, user)
    _validate_type(type)
    if end is None:
        end = dt.date.today().strftime("%Y-%m")
    end_first, end_last = _parse_month(end)
    # Walk back N-1 months from the end month.
    month_keys: list[str] = []
    cursor = end_first
    for _ in range(months):
        month_keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - dt.timedelta(days=1)).replace(day=1)
    month_keys.reverse()
    start_first = dt.datetime.strptime(month_keys[0], "%Y-%m").date()

    q = (
        db.query(
            func.to_char(
                func.date_trunc("month", cast(models.Transaction.occurred_on, Date)), "YYYY-MM"
            ).label("month"),
            func.sum(models.Transaction.amount).label("total"),
        )
        .filter(
            models.Transaction.space_id == space_id,
            models.Transaction.type == type,
            models.Transaction.occurred_on >= start_first,
            models.Transaction.occurred_on <= end_last,
        )
    )
    q = apply_category_filters(db, q, space_id, category_ids, exclude_category_ids)
    rows = q.group_by("month").all()
    totals = {r.month: float(r.total) for r in rows}
    return [{"month": m, "total": totals.get(m, 0.0)} for m in month_keys]
