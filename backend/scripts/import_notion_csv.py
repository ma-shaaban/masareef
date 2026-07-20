"""CLI wrapper around app.services.notion_import — import the owner's
Notion مصاريف CSV export into a masareef space.

Usage (from backend/, with DB_* env vars pointing at the TARGET database):

    python -m scripts.import_notion_csv --csv masareef.csv \
        --email you@example.com --space "Family" [--dry-run]

The mapping (tags → categories / payment methods) is documented in
app/services/notion_import.py. NOT idempotent: run once against a fresh
space. Never touches Notion.
"""

import argparse
import csv
import sys

from sqlalchemy.orm import sessionmaker

from app import models
from app.db import get_engine
from app.services.notion_import import import_csv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--email", required=True, help="owner account email in masareef")
    ap.add_argument("--space", required=True, help="target space name (must exist)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    db = SessionLocal()
    try:
        user = (
            db.query(models.User).filter(models.User.email == args.email.lower()).one_or_none()
        )
        if user is None:
            print(f"no user {args.email}", file=sys.stderr)
            return 1
        space = (
            db.query(models.Space)
            .join(models.SpaceMember, models.SpaceMember.space_id == models.Space.id)
            .filter(models.SpaceMember.user_id == user.id, models.Space.name == args.space)
            .one_or_none()
        )
        if space is None:
            print(f"no space named {args.space!r} for {args.email}", file=sys.stderr)
            return 1
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            stats = import_csv(
                db, csv.DictReader(f), space, paid_by=user.id, created_by=user.id
            )
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(("DRY RUN — nothing written. " if args.dry_run else "") + str(stats))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
