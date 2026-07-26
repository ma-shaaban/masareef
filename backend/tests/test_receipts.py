"""Receipt photo upload / fetch / delete on a transaction."""

# 1x1 PNG and a tiny JPEG header are enough — the endpoint only checks the
# declared content-type, not pixel validity.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000100057f2d3f0000000049454e44ae426082"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def setup_space(client, email="ana@example.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "sup3rsecret", "display_name": "Ana"},
    )
    return client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()


def add_tx(client, space_id, **body):
    body.setdefault("amount", 10)
    return client.post(f"/api/spaces/{space_id}/transactions", json=body).json()


def upload(client, tx_id, data=PNG_BYTES, mime="image/png"):
    return client.post(
        f"/api/transactions/{tx_id}/receipt", content=data, headers={"content-type": mime}
    )


def test_upload_get_roundtrip(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    r = upload(client, tx["id"])
    assert r.status_code == 200, r.text
    assert r.json()["mime"] == "image/png"
    assert r.json()["size"] == len(PNG_BYTES)

    got = client.get(f"/api/transactions/{tx['id']}/receipt")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content == PNG_BYTES


def test_has_receipt_flag(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    listed = client.get(f"/api/spaces/{space['id']}/transactions").json()["items"][0]
    assert listed["has_receipt"] is False
    upload(client, tx["id"])
    listed = client.get(f"/api/spaces/{space['id']}/transactions").json()["items"][0]
    assert listed["has_receipt"] is True


def test_replace_overwrites(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    upload(client, tx["id"], PNG_BYTES, "image/png")
    upload(client, tx["id"], JPEG_BYTES, "image/jpeg")
    got = client.get(f"/api/transactions/{tx['id']}/receipt")
    assert got.headers["content-type"] == "image/jpeg"
    assert got.content == JPEG_BYTES


def test_delete(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    upload(client, tx["id"])
    assert client.delete(f"/api/transactions/{tx['id']}/receipt").status_code == 204
    assert client.get(f"/api/transactions/{tx['id']}/receipt").status_code == 404
    listed = client.get(f"/api/spaces/{space['id']}/transactions").json()["items"][0]
    assert listed["has_receipt"] is False


def test_non_image_415(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    r = client.post(
        f"/api/transactions/{tx['id']}/receipt",
        content=b"not an image",
        headers={"content-type": "application/pdf"},
    )
    assert r.status_code == 415


def test_too_large_413(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    r = upload(client, tx["id"], b"\xff\xd8" + b"\x00" * (2_000_001), "image/jpeg")
    assert r.status_code == 413


def test_member_isolation_404(client, make_client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    upload(client, tx["id"])
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    )
    assert c2.post(
        f"/api/transactions/{tx['id']}/receipt", content=PNG_BYTES,
        headers={"content-type": "image/png"},
    ).status_code == 404
    assert c2.get(f"/api/transactions/{tx['id']}/receipt").status_code == 404
    assert c2.delete(f"/api/transactions/{tx['id']}/receipt").status_code == 404


def test_get_missing_404(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    assert client.get(f"/api/transactions/{tx['id']}/receipt").status_code == 404


def test_delete_transaction_cascades_receipt(client):
    space = setup_space(client)
    tx = add_tx(client, space["id"])
    upload(client, tx["id"])
    assert client.delete(f"/api/transactions/{tx['id']}").status_code == 204
    # receipt is gone with the transaction (tx now 404s anyway)
    assert client.get(f"/api/transactions/{tx['id']}/receipt").status_code == 404
