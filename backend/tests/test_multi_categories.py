"""Unified categories: a record carries an ordered list; first = main."""


def setup_space(client, email="ana@example.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": "Ana"},
    )
    space = client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()
    cats = {c["name"]: c for c in client.get(f"/api/spaces/{space['id']}/categories").json()}
    return space, cats


def add_tx(client, space_id, **body):
    return client.post(f"/api/spaces/{space_id}/transactions", json=body)


def test_ordered_multi_category(client):
    space, cats = setup_space(client)
    extra = client.post(
        f"/api/spaces/{space['id']}/categories", json={"name": "OneTime", "emoji": "⭐"}
    ).json()
    r = add_tx(
        client, space["id"], amount=150000,
        category_ids=[cats["Other"]["id"], extra["id"]],
    )
    assert r.status_code == 201
    names = [c["name"] for c in r.json()["categories"]]
    assert names == ["Other", "OneTime"]  # order preserved, main first


def test_duplicates_deduped(client):
    space, cats = setup_space(client)
    g = cats["Groceries"]["id"]
    r = add_tx(client, space["id"], amount=10, category_ids=[g, g])
    assert r.status_code == 201
    assert len(r.json()["categories"]) == 1


def test_filter_matches_any_position(client):
    space, cats = setup_space(client)
    add_tx(client, space["id"], amount=10,
           category_ids=[cats["Dining"]["id"], cats["Groceries"]["id"]])
    add_tx(client, space["id"], amount=20, category_ids=[cats["Dining"]["id"]])
    add_tx(client, space["id"], amount=30)
    r = client.get(
        f"/api/spaces/{space['id']}/transactions",
        params={"category_ids": [cats["Groceries"]["id"]]},
    ).json()
    assert r["total"] == 1
    assert r["items"][0]["amount"] == 10


def test_patch_replace_omit_clear(client):
    space, cats = setup_space(client)
    tx = add_tx(client, space["id"], amount=10, category_ids=[cats["Dining"]["id"]]).json()
    r = client.patch(
        f"/api/transactions/{tx['id']}", json={"category_ids": [cats["Health"]["id"]]}
    )
    assert [c["name"] for c in r.json()["categories"]] == ["Health"]
    r2 = client.patch(f"/api/transactions/{tx['id']}", json={"amount": 11})
    assert [c["name"] for c in r2.json()["categories"]] == ["Health"]  # unchanged
    r3 = client.patch(f"/api/transactions/{tx['id']}", json={"category_ids": []})
    assert r3.json()["categories"] == []


def test_foreign_category_in_list_422(client, make_client):
    space, _ = setup_space(client)
    c2 = make_client()
    _, cats2 = setup_space(c2, "bob@example.com")
    r = add_tx(client, space["id"], amount=10, category_ids=[cats2["Other"]["id"]])
    assert r.status_code == 422


def test_category_delete_in_use_any_position_409(client):
    space, cats = setup_space(client)
    add_tx(client, space["id"], amount=10,
           category_ids=[cats["Dining"]["id"], cats["Groceries"]["id"]])
    # secondary position still counts as "in use"
    assert client.delete(f"/api/categories/{cats['Groceries']['id']}").status_code == 409
