def setup_space(client, email="ana@example.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": "Ana"},
    )
    return client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()


def test_new_space_seeds_payment_methods(client):
    space = setup_space(client)
    pms = client.get(f"/api/spaces/{space['id']}/payment-methods").json()
    assert [p["name"] for p in pms] == ["Cash", "Card", "Bank", "Wallet"]
    assert pms[0]["icon"] == "💵"


def test_create_custom_payment_method(client):
    space = setup_space(client)
    r = client.post(
        f"/api/spaces/{space['id']}/payment-methods", json={"name": "Credit QNB", "icon": "💳"}
    )
    assert r.status_code == 201
    names = [p["name"] for p in client.get(f"/api/spaces/{space['id']}/payment-methods").json()]
    assert "Credit QNB" in names


def test_duplicate_name_409(client):
    space = setup_space(client)
    assert (
        client.post(f"/api/spaces/{space['id']}/payment-methods", json={"name": "cash"}).status_code
        == 409
    )


def test_archive_hides(client):
    space = setup_space(client)
    pms = client.get(f"/api/spaces/{space['id']}/payment-methods").json()
    wallet = next(p for p in pms if p["name"] == "Wallet")
    assert (
        client.patch(f"/api/payment-methods/{wallet['id']}", json={"is_archived": True}).status_code
        == 200
    )
    names = [p["name"] for p in client.get(f"/api/spaces/{space['id']}/payment-methods").json()]
    assert "Wallet" not in names


def test_delete_in_use_409_unused_ok(client):
    space = setup_space(client)
    pms = client.get(f"/api/spaces/{space['id']}/payment-methods").json()
    cash = next(p for p in pms if p["name"] == "Cash")
    bank = next(p for p in pms if p["name"] == "Bank")
    r = client.post(
        f"/api/spaces/{space['id']}/transactions",
        json={"amount": 10, "payment_method_id": cash["id"]},
    )
    assert r.status_code == 201
    assert client.delete(f"/api/payment-methods/{cash['id']}").status_code == 409
    assert client.delete(f"/api/payment-methods/{bank['id']}").status_code == 204


def test_non_member_404(client, make_client):
    space = setup_space(client)
    pms = client.get(f"/api/spaces/{space['id']}/payment-methods").json()
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    )
    assert c2.get(f"/api/spaces/{space['id']}/payment-methods").status_code == 404
    assert c2.patch(f"/api/payment-methods/{pms[0]['id']}", json={"name": "X"}).status_code == 404
