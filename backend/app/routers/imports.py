"""Member-only Notion CSV import over HTTPS — for one-time data migration
into a space when there's no direct database access (prod runs in-cluster).

Body: the raw CSV text of Notion's export (Name, Price, Date, Tags).
`dry_run=1` parses and maps without writing. `paid_by` attributes the
imported records to another member (e.g. the space owner) — defaults to
the caller. NOT idempotent: importing twice duplicates records."""

import csv
import io
import uuid

from fastapi import APIRouter, HTTPException, Request

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.spaces import get_membership
from app.services.notion_import import import_csv

router = APIRouter(prefix="/api", tags=["imports"])

MAX_BYTES = 5_000_000


@router.post("/spaces/{space_id}/import/notion-csv")
async def import_notion_csv(
    space_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    dry_run: bool = False,
    paid_by: uuid.UUID | None = None,
):
    get_membership(db, space_id, user)
    if paid_by is not None and db.get(models.SpaceMember, (space_id, paid_by)) is None:
        raise HTTPException(status_code=422, detail="paid_by must be a member of the space")
    body = await request.body()
    if len(body) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV too large (5 MB max)")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Body must be UTF-8 CSV text")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "Price" not in reader.fieldnames:
        raise HTTPException(
            status_code=422, detail="CSV must have a header row with at least a Price column"
        )
    space = db.get(models.Space, space_id)
    stats = import_csv(
        db, reader, space, paid_by=paid_by or user.id, created_by=user.id
    )
    if dry_run:
        db.rollback()
    return {"dry_run": dry_run, **stats}
