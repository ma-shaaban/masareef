"""Per-space expense categories."""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership

router = APIRouter(prefix="/api", tags=["categories"])


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(default="", max_length=8)
    color: str = Field(default="", max_length=9)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    emoji: str | None = Field(default=None, max_length=8)
    color: str | None = Field(default=None, max_length=9)
    sort_order: int | None = None
    is_archived: bool | None = None


def _category_json(c: models.Category) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "emoji": c.emoji,
        "color": c.color,
        "sort_order": c.sort_order,
        "is_archived": c.is_archived,
    }


def _get_category(db, category_id: uuid.UUID, user) -> models.Category:
    c = db.get(models.Category, category_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Category not found")
    get_membership(db, c.space_id, user)  # 404 for non-members
    return c


def _name_taken(db, space_id, name: str, except_id=None) -> bool:
    q = db.query(models.Category).filter(
        models.Category.space_id == space_id,
        models.Category.is_archived.is_(False),
        models.Category.name.ilike(name),
    )
    if except_id is not None:
        q = q.filter(models.Category.id != except_id)
    return db.query(q.exists()).scalar()


@router.get("/spaces/{space_id}/categories")
def list_categories(
    space_id: uuid.UUID, user: CurrentUser, db: DbSession, include_archived: bool = False
):
    get_membership(db, space_id, user)
    q = db.query(models.Category).filter(models.Category.space_id == space_id)
    if not include_archived:
        q = q.filter(models.Category.is_archived.is_(False))
    rows = q.order_by(models.Category.sort_order, models.Category.name).all()
    return [_category_json(c) for c in rows]


@router.post("/spaces/{space_id}/categories", status_code=201)
def create_category(space_id: uuid.UUID, body: CategoryCreate, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    name = body.name.strip()
    if _name_taken(db, space_id, name):
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    top = (
        db.query(models.Category.sort_order)
        .filter(models.Category.space_id == space_id)
        .order_by(models.Category.sort_order.desc())
        .limit(1)
        .scalar()
    )
    c = models.Category(
        space_id=space_id,
        name=name,
        emoji=body.emoji,
        color=body.color,
        sort_order=(top or 0) + 1,
    )
    db.add(c)
    db.flush()
    return _category_json(c)


@router.patch("/categories/{category_id}")
def patch_category(category_id: uuid.UUID, body: CategoryPatch, user: CurrentUser, db: DbSession):
    c = _get_category(db, category_id, user)
    if body.name is not None:
        name = body.name.strip()
        will_be_active = body.is_archived is False or (body.is_archived is None and not c.is_archived)
        if will_be_active and _name_taken(db, c.space_id, name, except_id=c.id):
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        c.name = name
    if body.emoji is not None:
        c.emoji = body.emoji
    if body.color is not None:
        c.color = body.color
    if body.sort_order is not None:
        c.sort_order = body.sort_order
    if body.is_archived is not None:
        if body.is_archived is False and _name_taken(db, c.space_id, c.name, except_id=c.id):
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        c.is_archived = body.is_archived
    return _category_json(c)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, user: CurrentUser, db: DbSession):
    c = _get_category(db, category_id, user)
    in_use = db.query(
        db.query(models.Transaction).filter(models.Transaction.category_id == c.id).exists()
    ).scalar()
    if in_use:
        raise HTTPException(status_code=409, detail="Category is in use; archive it instead")
    db.delete(c)
