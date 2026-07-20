"""Importer unit tests on a synthetic CSV shaped like Notion's export of the
real مصاريف DB (Name/Price/Date/Tags columns; Arabic names; mixed tags)."""

import csv
import io

from sqlalchemy.orm import sessionmaker

from app import models
from scripts.import_notion_csv import import_csv, parse_date, parse_price

CSV_TEXT = """Name,Price,Date,Tags,Attachment
صيدلية,935,"July 17, 2026",,
اوردر نون,"1,113","July 16, 2026",,
عشاء برة,250,"July 10, 2026","Restaurants&Cafes,Credit QNB",
دهب,150000,"June 5, 2026","Comex,OneTime",
قهوة السعودية,22.5,"May 2, 2026",SAR,
تبرعات,20000,"August 1, 2026",Charity,
سوبرماركت,780,2026-04-11,"Food,Credit CIB",
مجهول,,"July 16, 2026",,
هدية وشحن,500,"March 8, 2026","Gifts,Food",
"""


def _engine_session():
    from app.db import get_engine

    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


def setup_target(client):
    client.post(
        "/api/auth/signup",
        json={"email": "mah@example.com", "password": "sup3rsecret", "display_name": "Mahmoud"},
    )
    space = client.post(
        "/api/spaces", json={"name": "بيتنا", "kind": "household", "currency": "EGP"}
    ).json()
    return space


def run_import(client, dry_run=False):
    space_json = setup_target(client)
    db = _engine_session()
    try:
        user = db.query(models.User).filter(models.User.email == "mah@example.com").one()
        space = db.get(models.Space, space_json["id"])
        stats = import_csv(db, csv.DictReader(io.StringIO(CSV_TEXT)), user, space, dry_run=dry_run)
    finally:
        db.close()
    return space_json, stats


def test_parse_helpers():
    assert parse_date("July 17, 2026").isoformat() == "2026-07-17"
    assert parse_date("2026-04-11").isoformat() == "2026-04-11"
    assert parse_date("") is None
    assert str(parse_price("1,113")) == "1113.00"
    assert str(parse_price("22.5")) == "22.50"
    assert parse_price("") is None


def test_import_full_flow(client):
    space_json, stats = run_import(client)
    assert stats["imported"] == 8
    assert stats["skipped_no_price"] == 1
    assert stats["skipped_no_date"] == 0

    txs = client.get(
        f"/api/spaces/{space_json['id']}/transactions", params={"limit": 50}
    ).json()
    assert txs["total"] == 8

    by_desc = {t["description"]: t for t in txs["items"]}
    # untagged rows: no category, Cash payment
    assert by_desc["صيدلية"]["category"] is None
    assert by_desc["صيدلية"]["payment_method"]["name"] == "Cash"
    # thousands separator parsed
    assert by_desc["اوردر نون"]["amount"] == 1113
    # payment tag → payment method; category tag → category
    assert by_desc["عشاء برة"]["category"]["name"] == "Restaurants & Cafes"
    assert by_desc["عشاء برة"]["payment_method"]["name"] == "Credit QNB"
    # modifier tag stays a tag
    assert by_desc["دهب"]["category"]["name"] == "Comex"
    assert [t["name"] for t in by_desc["دهب"]["tags"]] == ["OneTime"]
    assert [t["name"] for t in by_desc["قهوة السعودية"]["tags"]] == ["SAR"]
    # future date imported as-is
    assert by_desc["تبرعات"]["occurred_on"] == "2026-08-01"
    # second category tag demoted to a plain tag
    assert by_desc["هدية وشحن"]["category"]["name"] == "Gifts"
    assert [t["name"] for t in by_desc["هدية وشحن"]["tags"]] == ["Food"]

    # created categories/pms visible in the space lists
    cat_names = {c["name"] for c in client.get(f"/api/spaces/{space_json['id']}/categories").json()}
    assert {"Restaurants & Cafes", "Comex", "Charity", "Gifts", "Food"} <= cat_names
    pm_names = {p["name"] for p in client.get(f"/api/spaces/{space_json['id']}/payment-methods").json()}
    assert {"Credit QNB", "Credit CIB", "Cash"} <= pm_names


def test_import_dry_run_writes_nothing(client):
    space_json, stats = run_import(client, dry_run=True)
    assert stats["imported"] == 8
    txs = client.get(f"/api/spaces/{space_json['id']}/transactions").json()
    assert txs["total"] == 0
