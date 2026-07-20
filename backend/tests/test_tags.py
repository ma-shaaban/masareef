def setup_space(client, email="ana@example.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": "Ana"},
    )
    return client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()


def add_tx(client, space_id, **body):
    return client.post(f"/api/spaces/{space_id}/transactions", json=body)


def test_tags_upsert_case_insensitive_on_create(client):
    space = setup_space(client)
    r1 = add_tx(client, space["id"], amount=10, tags=["OneTime", "SAR"])
    assert r1.status_code == 201
    assert sorted(t["name"] for t in r1.json()["tags"]) == ["OneTime", "SAR"]
    # same tag different case reuses the existing tag, no duplicate
    r2 = add_tx(client, space["id"], amount=20, tags=["onetime"])
    assert r2.json()["tags"][0]["name"] == "OneTime"
    tags = client.get(f"/api/spaces/{space['id']}/tags").json()
    assert sorted((t["name"], t["count"]) for t in tags) == [("OneTime", 2), ("SAR", 1)]


def test_filter_by_tag(client):
    space = setup_space(client)
    add_tx(client, space["id"], amount=10, tags=["OneTime"])
    add_tx(client, space["id"], amount=20)
    r = client.get(f"/api/spaces/{space['id']}/transactions", params={"tag": "onetime"}).json()
    assert r["total"] == 1
    assert r["items"][0]["amount"] == 10


def test_patch_replaces_tags(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"], amount=10, tags=["OneTime", "SAR"]).json()
    r = client.patch(f"/api/transactions/{tx['id']}", json={"tags": ["Work"]})
    assert r.status_code == 200
    assert [t["name"] for t in r.json()["tags"]] == ["Work"]
    # omitting tags leaves them unchanged
    r2 = client.patch(f"/api/transactions/{tx['id']}", json={"amount": 11})
    assert [t["name"] for t in r2.json()["tags"]] == ["Work"]
    # empty list clears
    r3 = client.patch(f"/api/transactions/{tx['id']}", json={"tags": []})
    assert r3.json()["tags"] == []


def test_arabic_tags_and_description(client):
    space = setup_space(client)
    r = add_tx(client, space["id"], amount=50, description="صيدلية", tags=["سفر"])
    assert r.status_code == 201
    assert r.json()["description"] == "صيدلية"
    assert r.json()["tags"][0]["name"] == "سفر"
    q = client.get(f"/api/spaces/{space['id']}/transactions", params={"q": "صيد"}).json()
    assert q["total"] == 1


def test_tags_isolated_per_space(client, make_client):
    space = setup_space(client)
    add_tx(client, space["id"], amount=10, tags=["OneTime"])
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    )
    space2 = c2.post(
        "/api/spaces", json={"name": "Shop", "kind": "shop", "currency": "EGP"}
    ).json()
    assert c2.get(f"/api/spaces/{space2['id']}/tags").json() == []
    assert c2.get(f"/api/spaces/{space['id']}/tags").status_code == 404
