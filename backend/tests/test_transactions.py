import datetime as dt


def setup_space(client, email="ana@example.com", name="Ana"):
    u = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": name},
    ).json()
    space = client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()
    cats = {c["name"]: c for c in client.get(f"/api/spaces/{space['id']}/categories").json()}
    return u, space, cats


def add_tx(client, space_id, **body):
    return client.post(f"/api/spaces/{space_id}/transactions", json=body)


def test_create_minimal_defaults(client):
    u, space, _ = setup_space(client)
    r = add_tx(client, space["id"], amount=125.5)
    assert r.status_code == 201
    tx = r.json()
    assert tx["amount"] == 125.5
    assert tx["type"] == "expense"
    assert tx["payment_method"]["name"] == "Cash"  # space's first method
    assert tx["occurred_on"] == dt.date.today().isoformat()
    assert tx["paid_by"] == u["id"]
    assert tx["category"] is None
    assert tx["description"] == ""
    assert tx["tags"] == []


def test_create_full(client):
    u, space, cats = setup_space(client)
    pms = {p["name"]: p for p in client.get(f"/api/spaces/{space['id']}/payment-methods").json()}
    r = add_tx(
        client,
        space["id"],
        amount=200,
        type="income",
        occurred_on="2026-07-01",
        category_id=cats["Other"]["id"],
        payment_method_id=pms["Bank"]["id"],
        description="salary bits",
    )
    assert r.status_code == 201
    tx = r.json()
    assert tx["type"] == "income"
    assert tx["category"]["name"] == "Other"
    assert tx["payment_method"]["name"] == "Bank"
    assert tx["paid_by_name"] == "Ana"


def test_amount_must_be_positive(client):
    _, space, _ = setup_space(client)
    assert add_tx(client, space["id"], amount=0).status_code == 422
    assert add_tx(client, space["id"], amount=-5).status_code == 422


def test_bad_type_and_foreign_payment_method_422(client, make_client):
    _, space, _ = setup_space(client)
    assert add_tx(client, space["id"], amount=5, type="loan").status_code == 422
    c2 = make_client()
    _, space2, _ = setup_space(c2, "eve@example.com", "Eve")
    other_pm = c2.get(f"/api/spaces/{space2['id']}/payment-methods").json()[0]
    assert (
        add_tx(client, space["id"], amount=5, payment_method_id=other_pm["id"]).status_code == 422
    )


def test_foreign_category_422(client, make_client):
    _, space, _ = setup_space(client)
    c2 = make_client()
    _, space2, cats2 = setup_space(c2, "bob@example.com", "Bob")
    r = add_tx(client, space["id"], amount=10, category_id=cats2["Other"]["id"])
    assert r.status_code == 422


def test_paid_by_must_be_member(client, make_client):
    _, space, _ = setup_space(client)
    c2 = make_client()
    bob, _, _ = setup_space(c2, "bob@example.com", "Bob")
    r = add_tx(client, space["id"], amount=10, paid_by=bob["id"])
    assert r.status_code == 422


def test_list_filters_and_pagination(client):
    _, space, cats = setup_space(client)
    add_tx(client, space["id"], amount=10, occurred_on="2026-07-01",
           category_id=cats["Groceries"]["id"], description="market run")
    add_tx(client, space["id"], amount=20, occurred_on="2026-07-05",
           category_id=cats["Dining"]["id"])
    add_tx(client, space["id"], amount=30, occurred_on="2026-06-20",
           category_id=cats["Groceries"]["id"])
    add_tx(client, space["id"], amount=99, occurred_on="2026-07-03", type="income")

    r = client.get(f"/api/spaces/{space['id']}/transactions")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert [t["amount"] for t in body["items"]] == [20, 99, 10, 30]  # newest occurred_on first

    by_range = client.get(
        f"/api/spaces/{space['id']}/transactions",
        params={"from": "2026-07-01", "to": "2026-07-31"},
    ).json()
    assert by_range["total"] == 3

    by_cat = client.get(
        f"/api/spaces/{space['id']}/transactions",
        params={"category_id": cats["Groceries"]["id"]},
    ).json()
    assert by_cat["total"] == 2

    by_type = client.get(
        f"/api/spaces/{space['id']}/transactions", params={"type": "income"}
    ).json()
    assert by_type["total"] == 1

    by_q = client.get(
        f"/api/spaces/{space['id']}/transactions", params={"q": "market"}
    ).json()
    assert by_q["total"] == 1

    paged = client.get(
        f"/api/spaces/{space['id']}/transactions", params={"limit": 2, "offset": 2}
    ).json()
    assert paged["total"] == 4
    assert len(paged["items"]) == 2


def test_filter_by_paid_by(client, make_client):
    _, space, _ = setup_space(client)
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    c2 = make_client()
    bob = c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    ).json()
    c2.post(f"/api/invites/{code}/accept")
    add_tx(client, space["id"], amount=10)
    add_tx(c2, space["id"], amount=20)
    r = client.get(
        f"/api/spaces/{space['id']}/transactions", params={"paid_by": bob["id"]}
    ).json()
    assert r["total"] == 1
    assert r["items"][0]["amount"] == 20
    assert r["items"][0]["paid_by_name"] == "Bob"


def test_patch_and_delete(client):
    _, space, cats = setup_space(client)
    tx = add_tx(client, space["id"], amount=10).json()
    r = client.patch(
        f"/api/transactions/{tx['id']}",
        json={"amount": 42.25, "category_id": cats["Health"]["id"], "description": "meds"},
    )
    assert r.status_code == 200
    assert r.json()["amount"] == 42.25
    assert r.json()["category"]["name"] == "Health"
    assert client.delete(f"/api/transactions/{tx['id']}").status_code == 204
    assert client.get(f"/api/spaces/{space['id']}/transactions").json()["total"] == 0


def test_cross_space_isolation(client, make_client):
    _, space, _ = setup_space(client)
    tx = add_tx(client, space["id"], amount=10).json()
    c2 = make_client()
    setup_space(c2, "bob@example.com", "Bob")
    assert c2.get(f"/api/spaces/{space['id']}/transactions").status_code == 404
    assert c2.patch(f"/api/transactions/{tx['id']}", json={"amount": 1}).status_code == 404
    assert c2.delete(f"/api/transactions/{tx['id']}").status_code == 404


def test_category_delete_in_use_409(client):
    _, space, cats = setup_space(client)
    add_tx(client, space["id"], amount=10, category_id=cats["Groceries"]["id"])
    r = client.delete(f"/api/categories/{cats['Groceries']['id']}")
    assert r.status_code == 409
    # archiving still works
    assert (
        client.patch(
            f"/api/categories/{cats['Groceries']['id']}", json={"is_archived": True}
        ).status_code
        == 200
    )
