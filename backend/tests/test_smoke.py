"""Template plumbing still works with the test DB wired in."""


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_db_check_ok(client):
    r = client.get("/api/db-check")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


def test_unknown_api_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}
