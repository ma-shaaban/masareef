def setup_space(client, email="ana@example.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": "Ana"},
    )
    return client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()


def test_list_seeded_ordered(client):
    space = setup_space(client)
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    assert [c["name"] for c in cats][:3] == ["Groceries", "Dining", "Transport"]
    assert all(not c["is_archived"] for c in cats)


def test_create_custom_category(client):
    space = setup_space(client)
    r = client.post(
        f"/api/spaces/{space['id']}/categories",
        json={"name": "Pets", "emoji": "🐾", "color": "#123456"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Pets"
    names = [c["name"] for c in client.get(f"/api/spaces/{space['id']}/categories").json()]
    assert "Pets" in names


def test_duplicate_name_409_case_insensitive(client):
    space = setup_space(client)
    r = client.post(f"/api/spaces/{space['id']}/categories", json={"name": "groceries"})
    assert r.status_code == 409


def test_archive_hides_from_default_list(client):
    space = setup_space(client)
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    groceries = next(c for c in cats if c["name"] == "Groceries")
    r = client.patch(f"/api/categories/{groceries['id']}", json={"is_archived": True})
    assert r.status_code == 200
    names = [c["name"] for c in client.get(f"/api/spaces/{space['id']}/categories").json()]
    assert "Groceries" not in names
    names_all = [
        c["name"]
        for c in client.get(
            f"/api/spaces/{space['id']}/categories", params={"include_archived": 1}
        ).json()
    ]
    assert "Groceries" in names_all


def test_delete_unused_ok(client):
    space = setup_space(client)
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    pets = client.post(f"/api/spaces/{space['id']}/categories", json={"name": "Pets"}).json()
    assert client.delete(f"/api/categories/{pets['id']}").status_code == 204
    names = [c["name"] for c in client.get(f"/api/spaces/{space['id']}/categories").json()]
    assert "Pets" not in names


def test_rename_and_edit(client):
    space = setup_space(client)
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    other = next(c for c in cats if c["name"] == "Other")
    r = client.patch(
        f"/api/categories/{other['id']}", json={"name": "Misc", "emoji": "🎈", "color": "#000000"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Misc"
    assert body["emoji"] == "🎈"
    assert body["color"] == "#000000"


def test_non_member_404(client, make_client):
    space = setup_space(client)
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    )
    assert c2.get(f"/api/spaces/{space['id']}/categories").status_code == 404
    assert c2.patch(f"/api/categories/{cats[0]['id']}", json={"name": "X"}).status_code == 404
    assert c2.delete(f"/api/categories/{cats[0]['id']}").status_code == 404
