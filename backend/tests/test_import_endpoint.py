"""Member-only HTTPS import endpoint (used for the one-time prod migration)."""

CSV_TEXT = """Name,Price,Date,Tags
صيدلية,935,"July 17, 2026",
دهب,150000,"June 5, 2026","Comex,OneTime,Credit CIB"
مجهول,,"July 16, 2026",
"""


def setup_owner_space(client):
    owner = client.post(
        "/api/auth/signup",
        json={"email": "owner@example.com", "password": "sup3rsecret", "display_name": "Owner"},
    ).json()
    space = client.post(
        "/api/spaces", json={"name": "Family", "kind": "household", "currency": "EGP"}
    ).json()
    return owner, space


def post_csv(client, space_id, text=CSV_TEXT, **params):
    return client.post(
        f"/api/spaces/{space_id}/import/notion-csv",
        params=params,
        content=text.encode(),
        headers={"content-type": "text/csv"},
    )


def test_dry_run_maps_but_writes_nothing(client):
    _, space = setup_owner_space(client)
    r = post_csv(client, space["id"], dry_run=1)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "dry_run": True,
        "imported": 2,
        "skipped_no_price": 1,
        "skipped_no_date": 0,
        "multi_category": 1,
    }
    assert client.get(f"/api/spaces/{space['id']}/transactions").json()["total"] == 0


def test_real_import_member_attributing_to_owner(client, make_client):
    owner, space = setup_owner_space(client)
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    helper = make_client()
    helper.post(
        "/api/auth/signup",
        json={"email": "helper@example.com", "password": "sup3rsecret", "display_name": "Helper"},
    )
    helper.post(f"/api/invites/{code}/accept")

    r = post_csv(helper, space["id"], paid_by=owner["id"])
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    txs = client.get(f"/api/spaces/{space['id']}/transactions").json()
    assert txs["total"] == 2
    assert all(t["paid_by_name"] == "Owner" for t in txs["items"])
    gold = next(t for t in txs["items"] if t["description"] == "دهب")
    assert [c["name"] for c in gold["categories"]] == ["Comex", "OneTime"]
    assert gold["payment_method"]["name"] == "Credit CIB"


def test_paid_by_must_be_member(client, make_client):
    _, space = setup_owner_space(client)
    c2 = make_client()
    stranger = c2.post(
        "/api/auth/signup",
        json={"email": "s@example.com", "password": "sup3rsecret", "display_name": "S"},
    ).json()
    r = post_csv(client, space["id"], paid_by=stranger["id"])
    assert r.status_code == 422


def test_non_member_404(client, make_client):
    _, space = setup_owner_space(client)
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "eve@example.com", "password": "sup3rsecret", "display_name": "Eve"},
    )
    assert post_csv(c2, space["id"]).status_code == 404


def test_missing_header_422(client):
    _, space = setup_owner_space(client)
    r = post_csv(client, space["id"], text="just,some,garbage\n1,2,3\n")
    assert r.status_code == 422


def test_oversized_body_413(client):
    _, space = setup_owner_space(client)
    big = "Name,Price,Date,Tags\n" + ("x,1,2026-01-01,\n" * 400000)
    r = post_csv(client, space["id"], text=big)
    assert r.status_code == 413
