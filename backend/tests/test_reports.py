"""Report endpoints against one fixed dataset with hand-computed expectations.

Dataset (space currency EGP, two members Ana + Bob):
  2026-07: groceries 100 (Ana), groceries 50 (Bob), dining 80 (Ana),
           uncategorized 20 (Ana), income 500 (Ana, bank)
  2026-06: groceries 200 (Ana), health 60 (Bob)
  2026-05: dining 90 (Ana)
July expense total = 250; June = 260; May = 90.
"""


def build_dataset(client, make_client):
    ana = client.post(
        "/api/auth/signup",
        json={"email": "ana@example.com", "password": "sup3rsecret", "display_name": "Ana"},
    ).json()
    space = client.post(
        "/api/spaces", json={"name": "Home", "kind": "household", "currency": "EGP"}
    ).json()
    cats = {c["name"]: c for c in client.get(f"/api/spaces/{space['id']}/categories").json()}
    code = client.post(f"/api/spaces/{space['id']}/invites").json()["code"]
    c2 = make_client()
    bob = c2.post(
        "/api/auth/signup",
        json={"email": "bob@example.com", "password": "sup3rsecret", "display_name": "Bob"},
    ).json()
    c2.post(f"/api/invites/{code}/accept")

    def add(cl, amount, day, cat=None, type_="expense", **kw):
        body = {"amount": amount, "occurred_on": day, "type": type_}
        if cat:
            names = cat if isinstance(cat, list) else [cat]
            body["category_ids"] = [cats[n]["id"] for n in names]
        body.update(kw)
        r = cl.post(f"/api/spaces/{space['id']}/transactions", json=body)
        assert r.status_code == 201, r.text

    add(client, 100, "2026-07-02", "Groceries")
    add(c2, 50, "2026-07-10", "Groceries")
    # multi-category: Dining is MAIN, Groceries is a secondary label
    add(client, 80, "2026-07-10", ["Dining", "Groceries"])
    add(client, 20, "2026-07-15")
    add(client, 500, "2026-07-01", None, "income")
    add(client, 200, "2026-06-05", "Groceries")
    add(c2, 60, "2026-06-20", "Health")
    add(client, 90, "2026-05-11", "Dining")
    return ana, bob, space, cats


def test_summary(client, make_client):
    _, _, space, _ = build_dataset(client, make_client)
    r = client.get(f"/api/spaces/{space['id']}/reports/summary", params={"month": "2026-07"})
    assert r.status_code == 200
    s = r.json()
    assert s["month"] == "2026-07"
    assert s["expense_total"] == 250
    assert s["income_total"] == 500
    assert s["prev_expense_total"] == 260
    daily = {d["date"]: d["total"] for d in s["daily"]}
    assert daily == {"2026-07-02": 100, "2026-07-10": 130, "2026-07-15": 20}


def test_summary_bad_month_422(client, make_client):
    _, _, space, _ = build_dataset(client, make_client)
    for bad in ("2026-13", "202607", "2026-7"):
        r = client.get(f"/api/spaces/{space['id']}/reports/summary", params={"month": bad})
        assert r.status_code == 422, bad


def test_by_category(client, make_client):
    _, _, space, cats = build_dataset(client, make_client)
    r = client.get(
        f"/api/spaces/{space['id']}/reports/by-category",
        params={"from": "2026-07-01", "to": "2026-07-31"},
    )
    assert r.status_code == 200
    rows = r.json()
    assert [x["name"] for x in rows] == ["Groceries", "Dining", "Uncategorized"]
    by_name = {x["name"]: x for x in rows}
    assert by_name["Groceries"]["total"] == 150
    assert by_name["Groceries"]["count"] == 2
    assert by_name["Groceries"]["pct"] == 60.0
    assert by_name["Dining"]["pct"] == 32.0
    assert by_name["Uncategorized"]["category_id"] is None
    assert by_name["Uncategorized"]["pct"] == 8.0


def test_by_member(client, make_client):
    ana, bob, space, _ = build_dataset(client, make_client)
    r = client.get(
        f"/api/spaces/{space['id']}/reports/by-member",
        params={"from": "2026-07-01", "to": "2026-07-31"},
    )
    rows = {x["display_name"]: x for x in r.json()}
    assert rows["Ana"]["total"] == 200
    assert rows["Bob"]["total"] == 50
    assert rows["Ana"]["user_id"] == ana["id"]


def test_monthly(client, make_client):
    _, _, space, _ = build_dataset(client, make_client)
    r = client.get(
        f"/api/spaces/{space['id']}/reports/monthly", params={"months": 4, "end": "2026-07"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 4
    by_month = {x["month"]: x["total"] for x in rows}
    assert by_month.get("2026-07") == 250
    assert by_month.get("2026-06") == 260
    assert by_month.get("2026-05") == 90
    assert by_month.get("2026-04") == 0  # zero-filled


def test_reports_non_member_404(client, make_client):
    _, _, space, _ = build_dataset(client, make_client)
    c3 = make_client()
    c3.post(
        "/api/auth/signup",
        json={"email": "eve@example.com", "password": "sup3rsecret", "display_name": "Eve"},
    )
    for path in ("summary?month=2026-07", "by-category", "by-member", "monthly"):
        assert c3.get(f"/api/spaces/{space['id']}/reports/{path}").status_code == 404, path


def test_reports_filtered_by_category(client, make_client):
    """category_id matches ANY position; the Dining-main record carries
    Groceries as a secondary label, so Groceries-filtered July = 100+50+80."""
    ana, bob, space, cats = build_dataset(client, make_client)
    g = cats["Groceries"]["id"]

    s = client.get(
        f"/api/spaces/{space['id']}/reports/summary",
        params={"month": "2026-07", "category_ids": [g]},
    ).json()
    assert s["expense_total"] == 230
    assert s["income_total"] == 0  # incomes carry no category
    assert s["prev_expense_total"] == 200
    assert {d["date"]: d["total"] for d in s["daily"]} == {
        "2026-07-02": 100,
        "2026-07-10": 130,
    }

    members = client.get(
        f"/api/spaces/{space['id']}/reports/by-member",
        params={"from": "2026-07-01", "to": "2026-07-31", "category_ids": [g]},
    ).json()
    assert {m["display_name"]: m["total"] for m in members} == {"Ana": 180, "Bob": 50}

    monthly = client.get(
        f"/api/spaces/{space['id']}/reports/monthly",
        params={"months": 4, "end": "2026-07", "category_ids": [g]},
    ).json()
    assert {m["month"]: m["total"] for m in monthly} == {
        "2026-07": 230,
        "2026-06": 200,
        "2026-05": 0,
        "2026-04": 0,
    }

    # by-category with the filter: matching records grouped by MAIN category
    rows = client.get(
        f"/api/spaces/{space['id']}/reports/by-category",
        params={"from": "2026-07-01", "to": "2026-07-31", "category_ids": [g]},
    ).json()
    assert {r["name"]: r["total"] for r in rows} == {"Groceries": 150, "Dining": 80}


def test_report_category_filter_foreign_422(client, make_client):
    _, _, space, _ = build_dataset(client, make_client)
    c3 = make_client()
    c3.post(
        "/api/auth/signup",
        json={"email": "zed@example.com", "password": "sup3rsecret", "display_name": "Zed"},
    )
    space2 = c3.post(
        "/api/spaces", json={"name": "Z", "kind": "shop", "currency": "EGP"}
    ).json()
    foreign_cat = c3.get(f"/api/spaces/{space2['id']}/categories").json()[0]["id"]
    r = client.get(
        f"/api/spaces/{space['id']}/reports/summary",
        params={"month": "2026-07", "category_ids": [foreign_cat]},
    )
    assert r.status_code == 422
