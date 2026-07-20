def signup(client, email, name="Someone"):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": name},
    )
    assert r.status_code == 201
    return r.json()


def make_space(client, name="Home", **overrides):
    body = {"name": name, "kind": "household", "currency": "EGP"}
    body.update(overrides)
    r = client.post("/api/spaces", json=body)
    assert r.status_code == 201
    return r.json()


def test_create_space_seeds_categories_and_owner(client):
    signup(client, "ana@example.com", "Ana")
    space = make_space(client)
    assert space["name"] == "Home"
    assert space["currency"] == "EGP"
    assert space["role"] == "owner"
    cats = client.get(f"/api/spaces/{space['id']}/categories").json()
    assert len(cats) == 10
    assert {"Groceries", "Other"} <= {c["name"] for c in cats}
    members = client.get(f"/api/spaces/{space['id']}/members").json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


def test_spaces_lists_only_mine(client, make_client):
    signup(client, "ana@example.com")
    make_space(client, "Ana home")
    c2 = make_client()
    signup(c2, "bob@example.com")
    make_space(c2, "Bob shop", kind="shop")
    names = [s["name"] for s in client.get("/api/spaces").json()]
    assert names == ["Ana home"]


def test_non_member_gets_404_not_403(client, make_client):
    signup(client, "ana@example.com")
    space = make_space(client)
    c2 = make_client()
    signup(c2, "bob@example.com")
    assert c2.get(f"/api/spaces/{space['id']}").status_code == 404
    assert c2.get(f"/api/spaces/{space['id']}/categories").status_code == 404
    assert c2.get(f"/api/spaces/{space['id']}/members").status_code == 404


def test_invite_accept_flow(client, make_client):
    signup(client, "ana@example.com")
    space = make_space(client)
    invite = client.post(f"/api/spaces/{space['id']}/invites").json()
    assert invite["code"]

    c2 = make_client()
    signup(c2, "bob@example.com", "Bob")
    preview = c2.get(f"/api/invites/{invite['code']}")
    assert preview.status_code == 200
    assert preview.json()["space_name"] == "Home"
    r = c2.post(f"/api/invites/{invite['code']}/accept")
    assert r.status_code == 200
    assert r.json()["id"] == space["id"]
    # bob is now a member; accepting again is idempotent
    assert c2.post(f"/api/invites/{invite['code']}/accept").status_code == 200
    members = c2.get(f"/api/spaces/{space['id']}/members").json()
    assert len(members) == 2


def test_revoked_invite_404(client, make_client):
    signup(client, "ana@example.com")
    space = make_space(client)
    invite = client.post(f"/api/spaces/{space['id']}/invites").json()
    assert client.delete(f"/api/spaces/{space['id']}/invites/{invite['id']}").status_code == 204
    c2 = make_client()
    signup(c2, "bob@example.com")
    assert c2.get(f"/api/invites/{invite['code']}").status_code == 404
    assert c2.post(f"/api/invites/{invite['code']}/accept").status_code == 404


def test_member_can_leave_owner_can_remove(client, make_client):
    signup(client, "ana@example.com")
    space = make_space(client)
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    c2 = make_client()
    bob = signup(c2, "bob@example.com")
    c2.post(f"/api/invites/{code}/accept")
    # bob leaves
    assert c2.delete(f"/api/spaces/{space['id']}/members/{bob['id']}").status_code == 204
    assert c2.get(f"/api/spaces/{space['id']}").status_code == 404
    # bob rejoins, ana (owner) removes him
    c2.post(f"/api/invites/{code}/accept")
    assert client.delete(f"/api/spaces/{space['id']}/members/{bob['id']}").status_code == 204
    members = client.get(f"/api/spaces/{space['id']}/members").json()
    assert len(members) == 1


def test_member_cannot_remove_other_member(client, make_client):
    ana = signup(client, "ana@example.com")
    space = make_space(client)
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    c2 = make_client()
    signup(c2, "bob@example.com")
    c2.post(f"/api/invites/{code}/accept")
    assert c2.delete(f"/api/spaces/{space['id']}/members/{ana['id']}").status_code == 403


def test_last_owner_cannot_leave(client):
    ana = signup(client, "ana@example.com")
    space = make_space(client)
    r = client.delete(f"/api/spaces/{space['id']}/members/{ana['id']}")
    assert r.status_code == 409


def test_owner_patches_space_member_cannot(client, make_client):
    signup(client, "ana@example.com")
    space = make_space(client)
    r = client.patch(f"/api/spaces/{space['id']}", json={"currency": "USD", "name": "Casa"})
    assert r.status_code == 200
    assert r.json()["currency"] == "USD"
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    c2 = make_client()
    signup(c2, "bob@example.com")
    c2.post(f"/api/invites/{code}/accept")
    assert c2.patch(f"/api/spaces/{space['id']}", json={"name": "Bobs"}).status_code == 403
