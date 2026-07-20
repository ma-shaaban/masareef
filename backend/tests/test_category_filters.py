"""Multi include / exclude category filters on listing + reports.

Dataset: g=Groceries-only 10, d=Dining-only 20, gd=[Dining main, Groceries] 40,
u=uncategorized 5 — all July 2026.
"""


def setup(client):
    client.post(
        "/api/auth/signup",
        json={"email": "ana@example.com", "password": "sup3rsecret", "display_name": "Ana"},
    )
    space = client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()
    cats = {c["name"]: c["id"] for c in client.get(f"/api/spaces/{space['id']}/categories").json()}

    def add(amount, day, names=()):
        r = client.post(
            f"/api/spaces/{space['id']}/transactions",
            json={
                "amount": amount,
                "occurred_on": day,
                "category_ids": [cats[n] for n in names],
            },
        )
        assert r.status_code == 201, r.text

    add(10, "2026-07-01", ["Groceries"])
    add(20, "2026-07-02", ["Dining"])
    add(40, "2026-07-03", ["Dining", "Groceries"])
    add(5, "2026-07-04")
    return space, cats


def list_totals(client, space, **params):
    r = client.get(f"/api/spaces/{space['id']}/transactions", params=params)
    assert r.status_code == 200, r.text
    return sorted(t["amount"] for t in r.json()["items"])


def test_include_multiple_is_any_of(client):
    space, cats = setup(client)
    assert list_totals(
        client, space, category_ids=[cats["Groceries"], cats["Dining"]]
    ) == [10, 20, 40]


def test_exclude_keeps_uncategorized(client):
    space, cats = setup(client)
    assert list_totals(client, space, exclude_category_ids=[cats["Dining"]]) == [5, 10]


def test_include_and_exclude_combined(client):
    space, cats = setup(client)
    # has Dining but not Groceries → only the Dining-only record
    assert list_totals(
        client, space,
        category_ids=[cats["Dining"]],
        exclude_category_ids=[cats["Groceries"]],
    ) == [20]


def test_foreign_id_422_in_either_list(client, make_client):
    space, _ = setup(client)
    c2 = make_client()
    c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    )
    space2 = c2.post(
        "/api/spaces", json={"name": "S2", "kind": "shop", "currency": "EGP"}
    ).json()
    foreign = c2.get(f"/api/spaces/{space2['id']}/categories").json()[0]["id"]
    for key in ("category_ids", "exclude_category_ids"):
        r = client.get(f"/api/spaces/{space['id']}/transactions", params={key: [foreign]})
        assert r.status_code == 422, key


def test_report_summary_include_and_exclude(client):
    space, cats = setup(client)
    inc = client.get(
        f"/api/spaces/{space['id']}/reports/summary",
        params={"month": "2026-07", "category_ids": [cats["Groceries"], cats["Dining"]]},
    ).json()
    assert inc["expense_total"] == 70
    exc = client.get(
        f"/api/spaces/{space['id']}/reports/summary",
        params={"month": "2026-07", "exclude_category_ids": [cats["Dining"]]},
    ).json()
    assert exc["expense_total"] == 15


def test_report_by_category_respects_filters(client):
    space, cats = setup(client)
    rows = client.get(
        f"/api/spaces/{space['id']}/reports/by-category",
        params={
            "from": "2026-07-01",
            "to": "2026-07-31",
            "exclude_category_ids": [cats["Groceries"]],
        },
    ).json()
    # Groceries-only (10) and the multi record (40, carries Groceries) drop out
    assert {r["name"]: r["total"] for r in rows} == {"Dining": 20, "Uncategorized": 5}


def test_report_monthly_and_by_member_accept_filters(client):
    space, cats = setup(client)
    monthly = client.get(
        f"/api/spaces/{space['id']}/reports/monthly",
        params={"months": 1, "end": "2026-07", "category_ids": [cats["Dining"]]},
    ).json()
    assert monthly == [{"month": "2026-07", "total": 60}]
    members = client.get(
        f"/api/spaces/{space['id']}/reports/by-member",
        params={
            "from": "2026-07-01",
            "to": "2026-07-31",
            "exclude_category_ids": [cats["Dining"]],
        },
    ).json()
    assert members[0]["total"] == 15
