import pytest

from app import security


@pytest.fixture(autouse=True)
def reset_rate_limit():
    security.reset_rate_limit()
    yield
    security.reset_rate_limit()


def signup(client, email="ana@example.com", password="sup3rsecret", name="Ana", **kw):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": name},
        **kw,
    )


def test_signup_sets_cookie_and_me_works(client):
    r = signup(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "ana@example.com"
    assert body["display_name"] == "Ana"
    assert "password" not in body and "password_hash" not in body
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"


def test_signup_duplicate_email_409_case_insensitive(client):
    assert signup(client).status_code == 201
    r = signup(client, email="ANA@example.com")
    assert r.status_code == 409


def test_signup_short_password_422(client):
    r = signup(client, password="short")
    assert r.status_code == 422


def test_login_ok(client, make_client):
    signup(client)
    c2 = make_client()
    r = c2.post("/api/auth/login", json={"email": "Ana@Example.com", "password": "sup3rsecret"})
    assert r.status_code == 200
    assert c2.get("/api/auth/me").status_code == 200


def test_login_wrong_password_and_unknown_email_same_answer(client):
    signup(client)
    r1 = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrongwrong"})
    r2 = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"})
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_login_rate_limited_429(client):
    signup(client)
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrongwrong"})
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "sup3rsecret"})
    assert r.status_code == 429


def test_logout_clears_session(client):
    signup(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_patch_display_name(client):
    signup(client)
    r = client.patch("/api/auth/me", json={"display_name": "Ana Maria"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ana Maria"


def test_me_unauthenticated_401(client):
    assert client.get("/api/auth/me").status_code == 401
