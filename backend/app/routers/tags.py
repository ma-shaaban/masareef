"""Per-space tags (read side; tags are created implicitly via transactions)."""

import uuid

from fastapi import APIRouter
from sqlalchemy import func

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership

router = APIRouter(prefix="/api", tags=["tags"])


@router.get("/spaces/{space_id}/tags")
def list_tags(space_id: uuid.UUID, user: CurrentUser, db: DbSession):
    get_membership(db, space_id, user)
    rows = (
        db.query(models.Tag, func.count(models.TransactionTag.transaction_id))
        .outerjoin(models.TransactionTag, models.TransactionTag.tag_id == models.Tag.id)
        .filter(models.Tag.space_id == space_id, models.Tag.is_archived.is_(False))
        .group_by(models.Tag.id)
        .order_by(func.count(models.TransactionTag.transaction_id).desc(), models.Tag.name)
        .all()
    )
    return [{"id": str(t.id), "name": t.name, "count": n} for t, n in rows]
