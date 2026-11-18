"""API tests for auth, transactions, import, budgets, goals, and isolation."""

from datetime import date
from io import BytesIO

from tests.conftest import register


def _category_id(client, name, tx_type):
    rows = client.get("/api/categories").json()
    for row in rows:
        if row["name"] == name and row["transaction_type"] == tx_type:
            return row["id"]
    raise AssertionError(name)


def test_register_login_and_user_isolation(client):
    first = register(client, "one@example.com", "One")
    client.post(
        "/api/transactions",
        json={
            "date": "2026-11-01",
            "description": "Salary",
            "amount": "50000",
            "type": "income",
            "category_id": _category_id(client, "Salary", "income"),
            "payment_method": "Net Banking",
        },
    )
    client.post("/api/auth/logout")
    second = register(client, "two@example.com", "Two")
    assert second["id"] != first["id"]
    listing = client.get("/api/transactions").json()
    assert listing["total"] == 0
    denied = client.get("/api/auth/me")
    assert denied.json()["email"] == "two@example.com"


def test_transaction_crud_updates_dashboard(client):
    register(client)
    food = _category_id(client, "Food and Dining", "expense")
    created = client.post(
        "/api/transactions",
        json={
            "date": date.today().isoformat(),
            "description": "Lunch",
            "amount": "250.50",
            "type": "expense",
            "category_id": food,
            "payment_method": "UPI",
        },
    )
    assert created.status_code == 201, created.text
    tx_id = created.json()["id"]
    dashboard = client.get("/api/dashboard?preset=this_month").json()
    assert dashboard["summary"]["expenses"] == "250.50"
    assert dashboard["summary"]["income"] == "0.00"
    edited = client.patch(f"/api/transactions/{tx_id}", json={"amount": "300", "description": "Team lunch"})
    assert edited.status_code == 200
    dashboard = client.get("/api/dashboard?preset=this_month").json()
    assert dashboard["summary"]["expenses"] == "300.00"
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 200
    dashboard = client.get("/api/dashboard?preset=this_month").json()
    assert dashboard["summary"]["expenses"] == "0.00"
    assert dashboard["summary"]["transaction_count"] == 0


def test_keyword_category_and_search(client):
    register(client)
    created = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-02",
            "description": "SWIGGY ORDER 4582",
            "amount": "430",
            "type": "expense",
            "payment_method": "UPI",
        },
    )
    body = created.json()
    assert body["category_name"] == "Food and Dining"
    assert body["prediction"]["source"] == "keyword"
    found = client.get("/api/transactions", params={"search": "swiggy", "type": "expense", "sort": "amount_desc"})
    assert found.json()["total"] == 1


def test_csv_import_preview_and_duplicates(client):
    register(client)
    csv_text = (
        "Date,Narration,Debit,Credit,Balance\n"
        "2026-10-01,SALARY ACME,,80000,80000\n"
        "2026-10-02,SWIGGY ORDER 11,450,,79550\n"
        "2026-10-02,SWIGGY ORDER 11,450,,79550\n"
        "not-a-date,BROKEN,,,\n"
    )
    upload = client.post(
        "/api/imports/analyse",
        files={"file": ("statement.csv", BytesIO(csv_text.encode()), "text/csv")},
    )
    assert upload.status_code == 200, upload.text
    analysed = upload.json()
    assert analysed["suggested_mapping"]["description"] == "Narration"
    preview = client.post(
        "/api/imports/preview",
        json={"preview_id": analysed["preview_id"], "mapping": analysed["suggested_mapping"]},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_rows"] == 4
    assert body["ready_rows"] == 2
    assert body["duplicate_rows"] == 1
    assert body["invalid_rows"] == 1
    swiggy = next(row for row in body["rows"] if row["description"].startswith("SWIGGY") and row["status"] == "ready")
    assert swiggy["category_name"] == "Food and Dining"
    saved = client.post("/api/imports/commit", json={"preview_id": analysed["preview_id"], "rows": []})
    assert saved.status_code == 200, saved.text
    assert saved.json()["successful_rows"] == 2
    history = client.get("/api/imports").json()
    assert history[0]["successful_rows"] == 2
    # Importing the same file again marks both good rows as duplicates.
    upload2 = client.post(
        "/api/imports/analyse",
        files={"file": ("statement.csv", BytesIO(csv_text.encode()), "text/csv")},
    )
    preview2 = client.post(
        "/api/imports/preview",
        json={"preview_id": upload2.json()["preview_id"], "mapping": upload2.json()["suggested_mapping"]},
    )
    assert preview2.json()["duplicate_rows"] == 3
    assert preview2.json()["ready_rows"] == 0


def test_user_rule_overrides_keyword(client):
    register(client)
    shopping = _category_id(client, "Shopping", "expense")
    rule = client.post("/api/category-rules", json={"pattern": "swiggy office", "category_id": shopping})
    assert rule.status_code == 201
    created = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-03",
            "description": "SWIGGY OFFICE LUNCH",
            "amount": "900",
            "type": "expense",
            "payment_method": "UPI",
        },
    )
    assert created.json()["category_name"] == "Shopping"
    assert created.json()["prediction"]["source"] == "user_rule"


def test_budgets_goals_and_alerts(client):
    register(client)
    food = _category_id(client, "Food and Dining", "expense")
    today = date.today()
    created = client.post(
        "/api/budgets",
        json={"category_id": food, "monthly_limit": "1000", "month": today.month, "year": today.year},
    )
    assert created.status_code == 201
    client.post(
        "/api/transactions",
        json={
            "date": today.isoformat(),
            "description": "Groceries wait no this is food",
            "amount": "900",
            "type": "expense",
            "category_id": food,
            "payment_method": "UPI",
        },
    )
    status = client.get("/api/budgets", params={"month": today.month, "year": today.year}).json()
    assert status["items"][0]["level"] in {"critical", "warn", "over"}
    assert status["items"][0]["utilisation"] == 90.0
    goal = client.post(
        "/api/goals",
        json={"name": "Laptop", "target_amount": "80000", "target_date": "2027-11-01"},
    )
    assert goal.status_code == 201
    goal_id = goal.json()["id"]
    updated = client.post(
        f"/api/goals/{goal_id}/contributions",
        json={"amount": "30000", "contributed_on": today.isoformat(), "note": "Bonus"},
    )
    assert updated.json()["current_amount"] == "30000.00"
    assert updated.json()["remaining_amount"] == "50000.00"
    assert float(updated.json()["required_monthly"]) > 0
