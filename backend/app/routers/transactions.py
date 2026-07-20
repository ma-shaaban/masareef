"""Transaction CRUD + filtered listing. Money is Numeric(14,2) in Postgres
and serialized as float at the API boundary (display app; two decimal places
survive float round-tripping at these magnitudes).

A record carries an ORDERED category list (position 0 = main; drives the
by-category report). `category_ids` on create/patch replaces the whole
ordered set; the list filter matches any position."""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership

router = APIRouter(prefix="/api", tags=["transactions"])

TYPES = {"expense", "income"}


class TxCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str = "expense"
    occurred_on: dt.date | None = None
    category_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    payment_method_id: uuid.UUID | None = None
    paid_by: uuid.UUID | None = None
    description: str = Field(default="", max_length=500)


class TxPatch(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str | None = None
    occurred_on: dt.date | None = None
    category_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    payment_method_id: uuid.UUID | None = None
    paid_by: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)


def _validate_type(type_: str | None) -> None:
    if type_ is not None and type_ not in TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(TYPES)}")


def validate_category(db: Session, space_id: uuid.UUID, category_id: uuid.UUID) -> None:
    c = db.get(models.Category, category_id)
    if c is None or c.space_id != space_id:
        raise HTTPException(status_code=422, detail="Unknown category for this space")


def apply_category_filters(
    db: Session,
    query,
    space_id: uuid.UUID,
    include_ids: list[uuid.UUID],
    exclude_ids: list[uuid.UUID],
):
    """ANY-of the included categories (any position) and NONE-of the
    excluded ones. Ids are validated against the space (422 otherwise)."""
    for cid in [*include_ids, *exclude_ids]:
        validate_category(db, space_id, cid)
    if include_ids:
        query = query.filter(
            models.Transaction.id.in_(
                db.query(models.TransactionCategory.transaction_id).filter(
                    models.TransactionCategory.category_id.in_(include_ids)
                )
            )
        )
    if exclude_ids:
        query = query.filter(
            ~models.Transaction.id.in_(
                db.query(models.TransactionCategory.transaction_id).filter(
                    models.TransactionCategory.category_id.in_(exclude_ids)
                )
            )
        )
    return query


def _dedupe(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _set_categories(db: Session, tx: models.Transaction, ids: list[uuid.UUID]) -> None:
    ids = _dedupe(ids)
    for cid in ids:
        validate_category(db, tx.space_id, cid)
    db.query(models.TransactionCategory).filter(
        models.TransactionCategory.transaction_id == tx.id
    ).delete()
    for pos, cid in enumerate(ids):
        db.add(
            models.TransactionCategory(transaction_id=tx.id, category_id=cid, position=pos)
        )


def _validate_payment_method(db: Session, space_id: uuid.UUID, pm_id: uuid.UUID | None) -> None:
    if pm_id is None:
        return
    p = db.get(models.PaymentMethod, pm_id)
    if p is None or p.space_id != space_id:
        raise HTTPException(status_code=422, detail="Unknown payment method for this space")


def _validate_paid_by(db: Session, space_id: uuid.UUID, paid_by: uuid.UUID | None) -> None:
    if paid_by is None:
        return
    if db.get(models.SpaceMember, (space_id, paid_by)) is None:
        raise HTTPException(status_code=422, detail="paid_by must be a member of the space")


def _default_payment_method_id(db: Session, space_id: uuid.UUID) -> uuid.UUID | None:
    return (
        db.query(models.PaymentMethod.id)
        .filter(
            models.PaymentMethod.space_id == space_id,
            models.PaymentMethod.is_archived.is_(False),
        )
        .order_by(models.PaymentMethod.sort_order)
        .limit(1)
        .scalar()
    )


def _categories_for(db: Session, tx_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    if not tx_ids:
        return {}
    rows = (
        db.query(models.TransactionCategory.transaction_id, models.Category)
        .join(models.Category, models.Category.id == models.TransactionCategory.category_id)
        .filter(models.TransactionCategory.transaction_id.in_(tx_ids))
        .order_by(models.TransactionCategory.position)
        .all()
    )
    out: dict[uuid.UUID, list[dict]] = {}
    for tx_id, c in rows:
        out.setdefault(tx_id, []).append(
            {"id": str(c.id), "name": c.name, "emoji": c.emoji, "color": c.color}
        )
    return out


def _tx_json(
    tx: models.Transaction,
    payer: models.User | None,
    pm: models.PaymentMethod | None,
    categories: list[dict],
) -> dict:
    return {
        "id": str(tx.id),
        "space_id": str(tx.space_id),
        "type": tx.type,
        "amount": float(tx.amount),
        "occurred_on": tx.occurred_on.isoformat(),
        "categories": categories,
        "payment_method": (
            {"id": str(pm.id), "name": pm.name, "icon": pm.icon} if pm is not None else None
        ),
        "paid_by": str(tx.paid_by) if tx.paid_by else None,
        "paid_by_name": payer.display_name if payer else None,
        "description": tx.description,
    }


def _base_query(db: Session):
    return (
        db.query(models.Transaction, models.User, models.PaymentMethod)
        .outerjoin(models.User, models.User.id == models.Transaction.paid_by)
        .outerjoin(
            models.PaymentMethod,
            models.PaymentMethod.id == models.Transaction.payment_method_id,
        )
    )


def _fetch_tx_json(db: Session, tx_id: uuid.UUID) -> dict:
    tx, payer, pm = _base_query(db).filter(models.Transaction.id == tx_id).one()
    return _tx_json(tx, payer, pm, _categories_for(db, [tx.id]).get(tx.id, []))


def _get_tx_or_404(db: Session, tx_id: uuid.UUID, user: models.User) -> models.Transaction:
    tx = db.get(models.Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    get_membership(db, tx.space_id, user)  # 404 for non-members
    return tx


@router.post("/spaces/{space_id}/transactions", status_code=201)
def create_transaction(space_id: uuid.UUID, body: TxCreate, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    _validate_type(body.type)
    _validate_payment_method(db, space_id, body.payment_method_id)
    _validate_paid_by(db, space_id, body.paid_by)
    tx = models.Transaction(
        space_id=space_id,
        type=body.type,
        amount=body.amount,
        occurred_on=body.occurred_on or dt.date.today(),
        payment_method_id=body.payment_method_id or _default_payment_method_id(db, space_id),
        paid_by=body.paid_by or user.id,
        description=body.description.strip(),
        created_by=user.id,
    )
    db.add(tx)
    db.flush()
    _set_categories(db, tx, body.category_ids)
    return _fetch_tx_json(db, tx.id)


@router.get("/spaces/{space_id}/transactions")
def list_transactions(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_: dt.date | None = Query(default=None, alias="from"),
    to: dt.date | None = None,
    category_ids: list[uuid.UUID] = Query(default=[]),
    exclude_category_ids: list[uuid.UUID] = Query(default=[]),
    payment_method_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    type: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    get_membership(db, space_id, user)
    _validate_type(type)
    query = _base_query(db).filter(models.Transaction.space_id == space_id)
    if from_ is not None:
        query = query.filter(models.Transaction.occurred_on >= from_)
    if to is not None:
        query = query.filter(models.Transaction.occurred_on <= to)
    query = apply_category_filters(db, query, space_id, category_ids, exclude_category_ids)
    if payment_method_id is not None:
        query = query.filter(models.Transaction.payment_method_id == payment_method_id)
    if paid_by is not None:
        query = query.filter(models.Transaction.paid_by == paid_by)
    if type is not None:
        query = query.filter(models.Transaction.type == type)
    if q:
        query = query.filter(models.Transaction.description.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(
            models.Transaction.occurred_on.desc(), models.Transaction.created_at.desc()
        )
        .limit(limit)
        .offset(offset)
        .all()
    )
    cats_by_tx = _categories_for(db, [tx.id for tx, _, _ in rows])
    return {
        "items": [_tx_json(tx, payer, pm, cats_by_tx.get(tx.id, [])) for tx, payer, pm in rows],
        "total": total,
    }


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: uuid.UUID, body: TxPatch, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    _validate_type(body.type)
    if body.payment_method_id is not None:
        _validate_payment_method(db, tx.space_id, body.payment_method_id)
        tx.payment_method_id = body.payment_method_id
    if body.paid_by is not None:
        _validate_paid_by(db, tx.space_id, body.paid_by)
        tx.paid_by = body.paid_by
    if body.amount is not None:
        tx.amount = body.amount
    if body.type is not None:
        tx.type = body.type
    if body.occurred_on is not None:
        tx.occurred_on = body.occurred_on
    if body.description is not None:
        tx.description = body.description.strip()
    if body.category_ids is not None:
        _set_categories(db, tx, body.category_ids)
    db.flush()
    return _fetch_tx_json(db, tx.id)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: uuid.UUID, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    db.delete(tx)
