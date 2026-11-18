"""Deterministic money maths shared by the dashboard, reports, and assistant tools."""

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models import Transaction
from app.money import D, money_str, pct


def query_transactions(db: Session, user_id: int, start: date, end: date):
    return (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )


def summarise(rows: list[Transaction]) -> dict:
    income = D(0)
    expense = D(0)
    for row in rows:
        amount = D(row.amount)
        if row.type == "income":
            income += amount
        else:
            expense += amount
    net = income - expense
    savings = net if net > 0 else D(0)
    return {
        "income": money_str(income),
        "expenses": money_str(expense),
        "balance": money_str(net),
        "savings": money_str(savings),
        "savings_rate": pct(savings, income),
        "transaction_count": len(rows),
    }


def category_totals(rows: list[Transaction], tx_type: str) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        if row.type != tx_type:
            continue
        name = row.category.name if row.category else "Other"
        bucket = buckets.setdefault(name, {"category": name, "amount": D(0), "count": 0, "category_id": row.category_id})
        bucket["amount"] += D(row.amount)
        bucket["count"] += 1
    total = sum((item["amount"] for item in buckets.values()), D(0))
    ranked = sorted(buckets.values(), key=lambda item: item["amount"], reverse=True)
    return [
        {
            "category": item["category"],
            "category_id": item["category_id"],
            "amount": money_str(item["amount"]),
            "count": item["count"],
            "share": pct(item["amount"], total),
        }
        for item in ranked
    ]


def monthly_series(rows: list[Transaction]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for row in rows:
        key = row.date.strftime("%Y-%m")
        bucket = buckets.setdefault(key, {"month": key, "income": D(0), "expenses": D(0)})
        if row.type == "income":
            bucket["income"] += D(row.amount)
        else:
            bucket["expenses"] += D(row.amount)
    series = []
    for key in sorted(buckets):
        item = buckets[key]
        net = item["income"] - item["expenses"]
        series.append(
            {
                "month": key,
                "income": money_str(item["income"]),
                "expenses": money_str(item["expenses"]),
                "savings": money_str(net if net > 0 else 0),
                "balance": money_str(net),
            }
        )
    return series


def weekly_spending(rows: list[Transaction]) -> list[dict]:
    buckets: dict[str, D] = defaultdict(lambda: D(0))
    for row in rows:
        if row.type != "expense":
            continue
        start = row.date.fromordinal(row.date.toordinal() - row.date.weekday())
        buckets[start.isoformat()] += D(row.amount)
    return [{"week": key, "amount": money_str(buckets[key])} for key in sorted(buckets)]


def largest_expense(rows: list[Transaction]) -> dict | None:
    expenses = [row for row in rows if row.type == "expense"]
    if not expenses:
        return None
    top = max(expenses, key=lambda row: D(row.amount))
    return {
        "id": top.id,
        "description": top.description,
        "amount": money_str(top.amount),
        "date": top.date.isoformat(),
        "category": top.category.name if top.category else "Other",
    }


def average_daily_spend(rows: list[Transaction], start: date, end: date) -> str:
    days = (end - start).days + 1
    spent = sum((D(row.amount) for row in rows if row.type == "expense"), D(0))
    if days <= 0:
        return money_str(0)
    return money_str(spent / days)


def compare_periods(current_rows: list[Transaction], previous_rows: list[Transaction]) -> dict:
    current = summarise(current_rows)
    previous = summarise(previous_rows)
    current_cats = {item["category"]: D(item["amount"]) for item in category_totals(current_rows, "expense")}
    previous_cats = {item["category"]: D(item["amount"]) for item in category_totals(previous_rows, "expense")}
    names = sorted(set(current_cats) | set(previous_cats))
    categories = []
    for name in names:
        now = current_cats.get(name, D(0))
        then = previous_cats.get(name, D(0))
        delta = now - then
        categories.append(
            {
                "category": name,
                "current": money_str(now),
                "previous": money_str(then),
                "delta": money_str(delta),
                "change_pct": pct(delta, then),
            }
        )
    categories.sort(key=lambda item: abs(D(item["delta"])), reverse=True)
    expense_delta = D(current["expenses"]) - D(previous["expenses"])
    income_delta = D(current["income"]) - D(previous["income"])
    current_rate = current["savings_rate"]
    previous_rate = previous["savings_rate"]
    rate_delta = None
    if current_rate is not None and previous_rate is not None:
        rate_delta = round(current_rate - previous_rate, 1)
    return {
        "current": current,
        "previous": previous,
        "expense_delta": money_str(expense_delta),
        "expense_change_pct": pct(expense_delta, previous["expenses"]),
        "income_delta": money_str(income_delta),
        "income_change_pct": pct(income_delta, previous["income"]),
        "savings_rate_delta": rate_delta,
        "categories": categories,
    }
