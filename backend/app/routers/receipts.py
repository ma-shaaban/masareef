"""Receipt photos: one image per transaction, bytes stored in Postgres.
Member-guarded (non-members get 404 like every other per-tx route)."""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from app import models
from app.deps import CurrentUser, DbSession
from app.routers.transactions import _get_tx_or_404

router = APIRouter(prefix="/api", tags=["receipts"])

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 2_000_000


@router.post("/transactions/{tx_id}/receipt")
async def upload_receipt(tx_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    mime = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Receipt must be a JPEG, PNG, or WebP image")
    body = await request.body()
    if len(body) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Receipt too large (2 MB max)")
    if not body:
        raise HTTPException(status_code=422, detail="Empty image")
    existing = (
        db.query(models.Receipt).filter(models.Receipt.transaction_id == tx.id).one_or_none()
    )
    if existing is None:
        db.add(
            models.Receipt(transaction_id=tx.id, mime=mime, bytes=body, size=len(body))
        )
    else:
        existing.mime = mime
        existing.bytes = body
        existing.size = len(body)
    return {"mime": mime, "size": len(body)}


@router.get("/transactions/{tx_id}/receipt")
def get_receipt(tx_id: uuid.UUID, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    receipt = (
        db.query(models.Receipt).filter(models.Receipt.transaction_id == tx.id).one_or_none()
    )
    if receipt is None:
        raise HTTPException(status_code=404, detail="No receipt")
    return Response(
        content=receipt.bytes,
        media_type=receipt.mime,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/transactions/{tx_id}/receipt", status_code=204)
def delete_receipt(tx_id: uuid.UUID, user: CurrentUser, db: DbSession):
    tx = _get_tx_or_404(db, tx_id, user)
    deleted = (
        db.query(models.Receipt).filter(models.Receipt.transaction_id == tx.id).delete()
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="No receipt")
