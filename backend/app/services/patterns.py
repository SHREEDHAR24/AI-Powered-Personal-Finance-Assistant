"""Spending patterns explained from the user's own rows."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Transaction
from app.money import D, money_str, pct
from app.services.categorizer import clean_text


FOOD_DELIVERY = ("swiggy", "zomato", "eatsure")


def spending_patterns(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    start = today - timedelta(days=90)
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.user_id == user_id, Transaction.date >= start, Transaction.date <= today)
        .all()
    )
    expenses = [row for row in rows if row.type == "expense"]
    findings = []

    weekend = D(0)
    weekday = D(0)
    weekend_days = set()
    weekday_days = set()
    for row in expenses:
        if row.date.weekday() >= 5:
            weekend += D(row.amount)
            weekend_days.add(row.date)
        else:
            weekday += D(row.amount)
            weekday_days.add(row.date)
    weekend_avg = weekend / len(weekend_days) if weekend_days else D(0)
    weekday_avg = weekday / len(weekday_days) if weekday_days else D(0)
    if weekend_days and weekday_days and weekday_avg > 0:
        change = pct(weekend_avg - weekday_avg, weekday_avg)
        if change is not None and abs(change) >= 20:
            direction = "higher" if change > 0 else "lower"
            findings.append(
                {
                    "title": f"Weekend spending is {abs(change)}% {direction} than weekdays",
                    "detail": (
                        f"Over the last 90 days the average weekend day was {money_str(weekend_avg)} "
                        f"and the average weekday was {money_str(weekday_avg)}."
                    ),
                }
            )

    delivery = [row for row in expenses if any(word in clean_text(row.description) for word in FOOD_DELIVERY)]
    if len(delivery) >= 6:
        total = sum((D(row.amount) for row in delivery), D(0))
        findings.append(
            {
                "title": f"{len(delivery)} food delivery orders in 90 days",
                "detail": f"Swiggy and Zomato narrations add up to {money_str(total)}.",
            }
        )

    subscriptions = [
        row for row in expenses if row.category and row.category.name == "Subscriptions"
    ]
    if subscriptions:
        total = sum((D(row.amount) for row in subscriptions), D(0))
        findings.append(
            {
                "title": "Subscription charges",
                "detail": f"Subscriptions total {money_str(total)} across {len(subscriptions)} transactions in the last 90 days.",
            }
        )

    small: dict[str, list[Transaction]] = defaultdict(list)
    for row in expenses:
        if D(row.amount) <= D(200):
            small[clean_text(row.description)[:40]].append(row)
    repeated = [(key, items) for key, items in small.items() if len(items) >= 5 and key]
    repeated.sort(key=lambda item: len(item[1]), reverse=True)
    if repeated:
        key, items = repeated[0]
        total = sum((D(row.amount) for row in items), D(0))
        findings.append(
            {
                "title": "Repeated small transactions",
                "detail": (
                    f"\"{items[0].description}\" appears {len(items)} times at {money_str(D(items[0].amount))} or less, "
                    f"totalling {money_str(total)}."
                ),
            }
        )

    return {"window": "last_90_days", "items": findings}
