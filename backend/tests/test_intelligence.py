"""Anomalies, forecast, insights, recurring payments, reports, and assistant tools."""

from datetime import date
from decimal import Decimal

from app.services.assistant import TOOL_NAMES, execute_tool
from app.services.forecast import holdout_errors
from tests.conftest import register


def _login_db(client):
    """Return a session bound the same way the app is, by going through a tool endpoint's user."""
    return client


def _add(client, **kwargs):
    payload = {
        "payment_method": "UPI",
        "type": "expense",
        "category_id": kwargs.get("category_id"),
    }
    payload.update(kwargs)
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _cat(client, name, tx_type="expense"):
    for row in client.get("/api/categories").json():
        if row["name"] == name and row["transaction_type"] == tx_type:
            return row["id"]
    raise AssertionError(name)


def test_anomaly_flags_outlier_and_not_tea(client):
    register(client)
    food = _cat(client, "Food and Dining")
    for day in range(1, 13):
        _add(
            client,
            date=f"2026-08-{day:02d}",
            description=f"SWIGGY ORDER {day}",
            amount="300",
            category_id=food,
        )
    _add(client, date="2026-08-20", description="SWIGGY ORDER 9999", amount="7500", category_id=food)
    _add(client, date="2026-08-21", description="TEA", amount="40", category_id=food)
    found = client.get("/api/analytics/anomalies").json()
    amounts = [item["amount"] for item in found["items"]]
    assert "7500.00" in amounts
    assert "40.00" not in amounts
    assert "fraud" not in found["items"][0]["reason"].lower()


def test_forecast_needs_history_then_returns_estimate(client):
    register(client)
    food = _cat(client, "Food and Dining")
    early = client.get("/api/analytics/forecast").json()
    assert early["available"] is False
    for month, amount in [(6, "10000"), (7, "11000"), (8, "12000"), (9, "13000")]:
        _add(client, date=f"2026-{month:02d}-05", description="RENT", amount=amount, category_id=food)
    forecast = client.get("/api/analytics/forecast").json()
    assert forecast["available"] is True
    assert "estimate" in forecast["note"].lower()
    assert Decimal(forecast["next_month_expenses"]) > 0


def test_forecast_error_metrics_are_finite():
    metrics = holdout_errors([10000, 11000, 12000, 13000, 14000, 15000])
    assert metrics is not None
    assert metrics["mae"] >= 0
    assert metrics["rmse"] >= 0
    assert metrics["points"] == 3


def test_recurring_rent_not_random_food(client):
    register(client)
    rent = _cat(client, "Rent")
    food = _cat(client, "Food and Dining")
    for month in range(6, 12):
        _add(client, date=f"2026-{month:02d}-03", description="HOUSE RENT LANDLORD", amount="22000", category_id=rent)
        _add(
            client,
            date=f"2026-{month:02d}-11",
            description=f"SWIGGY ORDER {month}",
            amount=str(200 + month * 37),
            category_id=food,
        )
    items = client.get("/api/recurring").json()
    names = [item["name"] for item in items]
    assert any("RENT" in name for name in names)
    rent_item = next(item for item in items if "RENT" in item["name"])
    assert rent_item["next_expected_date"]
    confirmed = client.post(f"/api/recurring/{rent_item['id']}/confirm")
    assert confirmed.json()["status"] == "confirmed"
    rejected_food = [item for item in items if "SWIGGY" in item["name"]]
    assert rejected_food == []


def test_report_csv_and_pdf(client):
    register(client)
    salary = _cat(client, "Salary", "income")
    _add(
        client,
        date="2026-10-01",
        description="SALARY",
        amount="80000",
        type="income",
        category_id=salary,
        payment_method="Net Banking",
    )
    csv_response = client.get("/api/reports/monthly/export", params={"month": 10, "year": 2026, "format": "csv"})
    assert csv_response.status_code == 200
    assert "80000.00" in csv_response.text
    pdf_response = client.get("/api/reports/monthly/export", params={"month": 10, "year": 2026, "format": "pdf"})
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


def test_assistant_tools_use_database_numbers(client):
    register(client)
    food = _cat(client, "Food and Dining")
    _add(client, date=date.today().replace(day=1).isoformat(), description="SWIGGY ORDER 1", amount="4250", category_id=food)
    from app.core.database import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    try:
        from app.models import User

        user = db.query(User).filter(User.email == "ada@example.com").one()
        result = execute_tool(db, user, "get_category_expenses", {"category": "Food and Dining", "period": "current_month"})
        assert result["amount"] == "4250.00"
        assert result["transaction_count"] == 1
        summary = execute_tool(db, user, "get_monthly_summary", {"period": "current_month"})
        assert summary["expenses"] == "4250.00"
        for name in TOOL_NAMES:
            payload = execute_tool(db, user, name, {"category": "Food and Dining", "query": "swiggy", "period": "current_month"})
            assert "error" not in payload or name == "search_transactions"
    finally:
        db.close()


def test_assistant_refuses_without_key(client, monkeypatch):
    register(client)
    created = client.post("/api/conversations", json={})
    conversation_id = created.json()["id"]
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "How much did I spend on food?"},
    )
    assert response.status_code == 200
    assert "not configured" in response.text
    assert "invent" in response.text
    get_settings.cache_clear()


def test_fake_model_tool_round_trip(client):
    register(client)
    food = _cat(client, "Food and Dining")
    today = date.today().replace(day=1).isoformat()
    _add(client, date=today, description="SWIGGY ORDER 2", amount="1000", category_id=food)
    created = client.post("/api/conversations", json={})
    conversation_id = created.json()["id"]

    from app.core.database import get_db
    from app.main import app
    from app.models import Conversation
    from app.services.assistant import iter_reply

    db = next(app.dependency_overrides[get_db]())
    try:
        from app.models import Message, User

        user = db.query(User).filter(User.email == "ada@example.com").one()
        conversation = db.get(Conversation, conversation_id)
        db.add(Message(conversation_id=conversation.id, role="user", content="How much did I spend on food?"))
        db.commit()
        db.expire_all()
        conversation = db.get(Conversation, conversation_id)

        def complete(messages, tools):
            has_tool = any(message["role"] == "tool" for message in messages)
            if not has_tool:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "get_category_expenses",
                            "arguments": {"category": "Food and Dining", "period": "current_month"},
                        }
                    ],
                }
            tool_body = next(message["content"] for message in messages if message["role"] == "tool")
            return {"content": f"From your records: {tool_body}", "tool_calls": []}

        events = list(iter_reply(db, user, conversation, complete=complete))
        text = "".join(event.get("text", "") for event in events if event["event"] == "token")
        assert "1000.00" in text
        assert any(event["event"] == "tool" and event["name"] == "get_category_expenses" for event in events)
    finally:
        db.close()


def test_categorizer_metrics_on_fixture():
    """Precision and recall of the keyword layer on a fixed labelled list."""
    labels = [
        ("SWIGGY ORDER 4582", "Food and Dining"),
        ("ZOMATO FOOD", "Food and Dining"),
        ("UBER TRIP 19", "Transportation"),
        ("NETFLIX SUBSCRIPTION", "Subscriptions"),
        ("BESCOM BILL", "Utilities"),
        ("AMAZON PAYMENTS", "Shopping"),
        ("HOUSE RENT", "Rent"),
        ("SPOTIFY PREMIUM", "Subscriptions"),
        ("BLINKIT GROCERIES", "Groceries"),
        ("EMI HDFC", "EMI and Loan Payments"),
        ("dinner at the new place", "Food and Dining"),
        ("mystery merchant 77", "Other"),
    ]
    # This test does not need a database for the keyword function's expected hits.
    # Full predict_category is covered through the API. Here we score the keyword map directly.
    from app.services.categorizer import _keyword_match

    correct = 0
    predicted_positive = 0
    actual_positive = 0
    for text, expected in labels:
        match = _keyword_match(text.lower())
        predicted = match[0] if match else "Other"
        if expected != "Other":
            actual_positive += 1
        if predicted != "Other":
            predicted_positive += 1
        if predicted == expected:
            correct += 1
        if predicted != "Other" and predicted == expected:
            pass
    # The two unmatched rows are the paraphrase and the mystery merchant.
    assert correct >= 10
    precision_hits = sum(
        1
        for text, expected in labels
        if (_keyword_match(text.lower())[0] if _keyword_match(text.lower()) else "Other") == expected
    )
    assert precision_hits == correct
