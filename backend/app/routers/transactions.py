"""Transaction CRUD + filtered listing. Money is Numeric(14,2) in Postgres
and serialized as float at the API boundary (display app; two decimal places
survive float round-tripping at these magnitudes)."""

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
PAYMENT_METHODS = {"cash", "card", "wallet", "bank", "other"}


class TxCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str = "expense"
    occurred_on: dt.date | None = None
    category_id: uuid.UUID | None = None
    payment_method: str = "cash"
    paid_by: uuid.UUID | None = None
    description: str = Field(default="", max_length=500)


class TxPatch(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str | None = None
    occurred_on: dt.date | None = None
    category_id: uuid.UUID | None = None
    payment_method: str | None = None
    paid_by: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)


def _validate_enums(type_: str | None, payment_method: str | None) -> None:
    if type_ is not None and type_ not in TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(TYPES)}")
    if payment_method is not None and payment_method not in PAYMENT_METHODS:
        raise HTTPException(
            status_code=422, detail=f"payment_method must be one of {sorted(PAYMENT_METHODS)}"
        )


def _validate_category(db: Session, space_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    c = db.get(models.Category, category_id)
    if c is None or c.space_id != space_id:
        raise HTTPException(status_code=422, detail="Unknown category for this space")


def _validate_paid_by(db: Session, space_id: uuid.UUID, paid_by: uuid.UUID | None) -> None:
    if paid_by is None:
        return
    if db.get(models.SpaceMember, (space_id, paid_by)) is None:
        raise HTTPException(status_code=422, detail="paid_by must be a member of the space")


def _tx_json(tx: models.Transaction, category: models.Category | None, payer: models.User | None) -> dict:
    return {
        "id": str(tx.id),
        "space_id": str(tx.space_id),
        "type": tx.type,
        "amount": float(tx.amount),
        "occurred_on": tx.occurred_on.isoformat(),
        "category": (
            {"id": str(category.id), "name": category.name, "emoji": category.emoji,
             "color": category.color}
            if category is not None
            else None
        ),
        "payment_method": tx.payment_method,
        "paid_by": str(tx.paid_by) if tx.paid_by else None,
        "paid_by_name": payer.display_name if payer else None,
        "description": tx.description,
    }


def _fetch_tx_json(db: Session, tx_id: uuid.UUID) -> dict:
    tx, category, payer = (
        db.query(models.Transaction, models.Category, models.User)
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .outerjoin(models.User, models.User.id == models.Transaction.paid_by)
        .filter(models.Transaction.id == tx_id)
        .one()
    )
    return _tx_json(tx, category, payer)


def _get_tx_or_404(db: Session, tx_id: uuid.UUID, user: models.User) -> models.Transaction:
    tx = db.get(models.Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    get_membership(db, tx.space_id, user)  # 404 for non-members
    return tx


@router.post("/spaces/{space_id}/transactions", status_code=201)
def create_transaction(space_id: uuid.UUID, body: TxCreate, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    _validate_enums(body.type, body.payment_method)
    _validate_category(db, space_id, body.category_id)
    _validate_paid_by(db, space_id, body.paid_by)
    tx = models.Transaction(
        space_id=space_id,
        type=body.type,
        amount=body.amount,
        occurred_on=body.occurred_on or dt.date.today(),
        category_id=body.category_id,
        payment_method=body.payment_method,
        paid_by=body.paid_by or user.id,
        description=body.description.strip(),
        created_by=user.id,
    )
    db.add(tx)
    db.flush()
    return _fetch_tx_json(db, tx.id)


@router.get("/spaces/{space_id}/transactions")
def list_transactions(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_: dt.date | None = Query(default=None, alias="from"),
    to: dt.date | None = None,
    category_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    type: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    get_membership(db, space_id, user)
    _validate_enums(type, None)
    query = (
        db.query(models.Transaction, models.Category, models.User)
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .outerjoin(models.User, models.User.id == models.Transaction.paid_by)
        .filter(models.Transaction.space_id == space_id)
    )
    if from_ is not None:
        query = query.filter(models.Transaction.occurred_on >= from_)
    if to is not None:
        query = query.filter(models.Transaction.occurred_on <= to)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
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
    return {"items": [_tx_json(tx, c, p) for tx, c, p in rows], "total": total}


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: uuid.UUID, body: TxPatch, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    _validate_enums(body.type, body.payment_method)
    if body.category_id is not None:
        _validate_category(db, tx.space_id, body.category_id)
        tx.category_id = body.category_id
    if body.paid_by is not None:
        _validate_paid_by(db, tx.space_id, body.paid_by)
        tx.paid_by = body.paid_by
    if body.amount is not None:
        tx.amount = body.amount
    if body.type is not None:
        tx.type = body.type
    if body.occurred_on is not None:
        tx.occurred_on = body.occurred_on
    if body.payment_method is not None:
        tx.payment_method = body.payment_method
    if body.description is not None:
        tx.description = body.description.strip()
    db.flush()
    return _fetch_tx_json(db, tx.id)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: uuid.UUID, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    db.delete(tx)
