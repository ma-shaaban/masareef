"""Per-space payment methods (Cash, cards, wallets — user-defined)."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership

router = APIRouter(prefix="/api", tags=["payment-methods"])


class PaymentMethodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = Field(default="", max_length=8)


class PaymentMethodPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    icon: str | None = Field(default=None, max_length=8)
    sort_order: int | None = None
    is_archived: bool | None = None


def _pm_json(p: models.PaymentMethod) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "icon": p.icon,
        "sort_order": p.sort_order,
        "is_archived": p.is_archived,
    }


def _get_pm(db, pm_id: uuid.UUID, user) -> models.PaymentMethod:
    p = db.get(models.PaymentMethod, pm_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    get_membership(db, p.space_id, user)
    return p


def _name_taken(db, space_id, name: str, except_id=None) -> bool:
    q = db.query(models.PaymentMethod).filter(
        models.PaymentMethod.space_id == space_id,
        models.PaymentMethod.is_archived.is_(False),
        models.PaymentMethod.name.ilike(name),
    )
    if except_id is not None:
        q = q.filter(models.PaymentMethod.id != except_id)
    return db.query(q.exists()).scalar()


@router.get("/spaces/{space_id}/payment-methods")
def list_payment_methods(
    space_id: uuid.UUID, user: CurrentUser, db: DbSession, include_archived: bool = False
):
    get_membership(db, space_id, user)
    q = db.query(models.PaymentMethod).filter(models.PaymentMethod.space_id == space_id)
    if not include_archived:
        q = q.filter(models.PaymentMethod.is_archived.is_(False))
    rows = q.order_by(models.PaymentMethod.sort_order, models.PaymentMethod.name).all()
    return [_pm_json(p) for p in rows]


@router.post("/spaces/{space_id}/payment-methods", status_code=201)
def create_payment_method(
    space_id: uuid.UUID, body: PaymentMethodCreate, user: CurrentUser, db: DbSession
):
    get_membership(db, space_id, user)
    name = body.name.strip()
    if _name_taken(db, space_id, name):
        raise HTTPException(status_code=409, detail="A payment method with this name already exists")
    top = (
        db.query(models.PaymentMethod.sort_order)
        .filter(models.PaymentMethod.space_id == space_id)
        .order_by(models.PaymentMethod.sort_order.desc())
        .limit(1)
        .scalar()
    )
    p = models.PaymentMethod(
        space_id=space_id, name=name, icon=body.icon, sort_order=(top or 0) + 1
    )
    db.add(p)
    db.flush()
    return _pm_json(p)


@router.patch("/payment-methods/{pm_id}")
def patch_payment_method(
    pm_id: uuid.UUID, body: PaymentMethodPatch, user: CurrentUser, db: DbSession
):
    p = _get_pm(db, pm_id, user)
    if body.name is not None:
        name = body.name.strip()
        will_be_active = body.is_archived is False or (
            body.is_archived is None and not p.is_archived
        )
        if will_be_active and _name_taken(db, p.space_id, name, except_id=p.id):
            raise HTTPException(
                status_code=409, detail="A payment method with this name already exists"
            )
        p.name = name
    if body.icon is not None:
        p.icon = body.icon
    if body.sort_order is not None:
        p.sort_order = body.sort_order
    if body.is_archived is not None:
        if body.is_archived is False and _name_taken(db, p.space_id, p.name, except_id=p.id):
            raise HTTPException(
                status_code=409, detail="A payment method with this name already exists"
            )
        p.is_archived = body.is_archived
    return _pm_json(p)


@router.delete("/payment-methods/{pm_id}", status_code=204)
def delete_payment_method(pm_id: uuid.UUID, user: CurrentUser, db: DbSession):
    p = _get_pm(db, pm_id, user)
    in_use = db.query(
        db.query(models.Transaction)
        .filter(models.Transaction.payment_method_id == p.id)
        .exists()
    ).scalar()
    if in_use:
        raise HTTPException(status_code=409, detail="Payment method is in use; archive it instead")
    db.delete(p)
