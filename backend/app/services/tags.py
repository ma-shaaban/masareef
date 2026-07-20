"""Tag upsert + attachment helpers shared by transaction endpoints and the
Notion importer."""

from sqlalchemy.orm import Session

from app import models


def upsert_tags(db: Session, space_id, names: list[str]) -> list[models.Tag]:
    """Resolve tag names to per-space Tag rows, creating missing ones.
    Matching is case-insensitive; the first-seen spelling wins. Blank and
    duplicate names are dropped; order of first appearance is kept."""
    seen: dict[str, str] = {}
    for raw in names:
        name = raw.strip()
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    if not seen:
        return []
    existing = (
        db.query(models.Tag)
        .filter(
            models.Tag.space_id == space_id,
            models.Tag.is_archived.is_(False),
        )
        .all()
    )
    by_lower = {t.name.lower(): t for t in existing}
    result = []
    for lower, name in seen.items():
        tag = by_lower.get(lower)
        if tag is None:
            tag = models.Tag(space_id=space_id, name=name)
            db.add(tag)
            db.flush()
        result.append(tag)
    return result


def set_transaction_tags(db: Session, tx: models.Transaction, names: list[str]) -> None:
    """Replace a transaction's tag set with the given names."""
    db.query(models.TransactionTag).filter(
        models.TransactionTag.transaction_id == tx.id
    ).delete()
    for tag in upsert_tags(db, tx.space_id, names):
        db.add(models.TransactionTag(transaction_id=tx.id, tag_id=tag.id))
