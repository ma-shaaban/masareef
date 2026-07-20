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
from app.services.tags import set_transaction_tags

router = APIRouter(prefix="/api", tags=["transactions"])

TYPES = {"expense", "income"}


class TxCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str = "expense"
    occurred_on: dt.date | None = None
    category_id: uuid.UUID | None = None
    payment_method_id: uuid.UUID | None = None
    paid_by: uuid.UUID | None = None
    description: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=20)


class TxPatch(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("999999999999.99"), decimal_places=2)
    type: str | None = None
    occurred_on: dt.date | None = None
    category_id: uuid.UUID | None = None
    payment_method_id: uuid.UUID | None = None
    paid_by: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = Field(default=None, max_length=20)


def _validate_type(type_: str | None) -> None:
    if type_ is not None and type_ not in TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(TYPES)}")


def _validate_category(db: Session, space_id: uuid.UUID, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    c = db.get(models.Category, category_id)
    if c is None or c.space_id != space_id:
        raise HTTPException(status_code=422, detail="Unknown category for this space")


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


def _tags_for(db: Session, tx_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    if not tx_ids:
        return {}
    rows = (
        db.query(models.TransactionTag.transaction_id, models.Tag)
        .join(models.Tag, models.Tag.id == models.TransactionTag.tag_id)
        .filter(models.TransactionTag.transaction_id.in_(tx_ids))
        .order_by(models.Tag.name)
        .all()
    )
    out: dict[uuid.UUID, list[dict]] = {}
    for tx_id, tag in rows:
        out.setdefault(tx_id, []).append({"id": str(tag.id), "name": tag.name})
    return out


def _tx_json(
    tx: models.Transaction,
    category: models.Category | None,
    payer: models.User | None,
    pm: models.PaymentMethod | None,
    tags: list[dict],
) -> dict:
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
        "payment_method": (
            {"id": str(pm.id), "name": pm.name, "icon": pm.icon} if pm is not None else None
        ),
        "paid_by": str(tx.paid_by) if tx.paid_by else None,
        "paid_by_name": payer.display_name if payer else None,
        "description": tx.description,
        "tags": tags,
    }


def _base_query(db: Session):
    return (
        db.query(models.Transaction, models.Category, models.User, models.PaymentMethod)
        .outerjoin(models.Category, models.Category.id == models.Transaction.category_id)
        .outerjoin(models.User, models.User.id == models.Transaction.paid_by)
        .outerjoin(
            models.PaymentMethod,
            models.PaymentMethod.id == models.Transaction.payment_method_id,
        )
    )


def _fetch_tx_json(db: Session, tx_id: uuid.UUID) -> dict:
    tx, category, payer, pm = _base_query(db).filter(models.Transaction.id == tx_id).one()
    return _tx_json(tx, category, payer, pm, _tags_for(db, [tx.id]).get(tx.id, []))


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
    _validate_category(db, space_id, body.category_id)
    _validate_payment_method(db, space_id, body.payment_method_id)
    _validate_paid_by(db, space_id, body.paid_by)
    tx = models.Transaction(
        space_id=space_id,
        type=body.type,
        amount=body.amount,
        occurred_on=body.occurred_on or dt.date.today(),
        category_id=body.category_id,
        payment_method_id=body.payment_method_id or _default_payment_method_id(db, space_id),
        paid_by=body.paid_by or user.id,
        description=body.description.strip(),
        created_by=user.id,
    )
    db.add(tx)
    db.flush()
    if body.tags:
        set_transaction_tags(db, tx, body.tags)
    return _fetch_tx_json(db, tx.id)


@router.get("/spaces/{space_id}/transactions")
def list_transactions(
    space_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_: dt.date | None = Query(default=None, alias="from"),
    to: dt.date | None = None,
    category_id: uuid.UUID | None = None,
    payment_method_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    type: str | None = None,
    tag: str | None = None,
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
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
    if payment_method_id is not None:
        query = query.filter(models.Transaction.payment_method_id == payment_method_id)
    if paid_by is not None:
        query = query.filter(models.Transaction.paid_by == paid_by)
    if type is not None:
        query = query.filter(models.Transaction.type == type)
    if tag:
        query = query.filter(
            models.Transaction.id.in_(
                db.query(models.TransactionTag.transaction_id)
                .join(models.Tag, models.Tag.id == models.TransactionTag.tag_id)
                .filter(models.Tag.space_id == space_id, models.Tag.name.ilike(tag))
            )
        )
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
    tags_by_tx = _tags_for(db, [tx.id for tx, _, _, _ in rows])
    return {
        "items": [
            _tx_json(tx, c, payer, pm, tags_by_tx.get(tx.id, [])) for tx, c, payer, pm in rows
        ],
        "total": total,
    }


@router.patch("/transactions/{tx_id}")
def patch_transaction(tx_id: uuid.UUID, body: TxPatch, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    _validate_type(body.type)
    if body.category_id is not None:
        _validate_category(db, tx.space_id, body.category_id)
        tx.category_id = body.category_id
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
    if body.tags is not None:
        set_transaction_tags(db, tx, body.tags)
    db.flush()
    return _fetch_tx_json(db, tx.id)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: uuid.UUID, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    db.delete(tx)
