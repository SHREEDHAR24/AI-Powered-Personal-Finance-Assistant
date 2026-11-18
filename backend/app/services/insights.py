"""Personal insights. Each card is backed by a computed comparison."""

from datetime import date

from sqlalchemy.orm import Session

from app.models import InsightDismissal
from app.money import D, money_str
from app.services.budgets import budget_status, current_budget_month
from app.services.finance import category_totals, compare_periods, query_transactions, summarise
from app.services.patterns import spending_patterns
from app.services.periods import month_bounds, previous_month


def _insight(key: str, observation: str, data: dict, comparison: str, explanation: str, action: str) -> dict:
    return {
        "key": key,
        "observation": observation,
        "data": data,
        "comparison_period": comparison,
        "explanation": explanation,
        "action": action,
    }


def generate_insights(db: Session, user, today: date | None = None) -> list[dict]:
    today = today or date.today()
    year, month = today.year, today.month
    start, end = month_bounds(year, month)
    end = min(end, today)
    prev_year, prev_month = previous_month(year, month)
    prev_start, prev_end = month_bounds(prev_year, prev_month)
    current_rows = query_transactions(db, user.id, start, end)
    previous_rows = query_transactions(db, user.id, prev_start, prev_end)
    comparison = compare_periods(current_rows, previous_rows)
    current_label = start.strftime("%B %Y")
    previous_label = prev_start.strftime("%B %Y")
    insights = []

    for item in comparison["categories"]:
        change = item["change_pct"]
        delta = D(item["delta"])
        if change is None or abs(change) < 15 or abs(delta) < D("200"):
            continue
        direction = "increased" if delta > 0 else "decreased"
        insights.append(
            _insight(
                key=f"mom:{year}-{month}:{item['category']}",
                observation=f"Your {item['category']} expenses {direction} by {abs(change)}% this month.",
                data={
                    "current": item["current"],
                    "previous": item["previous"],
                    "delta": item["delta"],
                },
                comparison=f"{current_label} vs {previous_label}",
                explanation=(
                    f"{item['category']} is {item['current']} so far in {current_label}, "
                    f"compared with {item['previous']} in {previous_label}."
                ),
                action=(
                    "Check the largest transactions in this category before the month ends."
                    if delta > 0
                    else "This category is lower than last month. The change is already in your transactions."
                ),
            )
        )

    sub_now = next((item for item in category_totals(current_rows, "expense") if item["category"] == "Subscriptions"), None)
    # Last three months of subscriptions, including the current partial month.
    from app.services.periods import add_months

    three_start = add_months(today.replace(day=1), -2)
    recent = query_transactions(db, user.id, three_start, today)
    sub_rows = [row for row in recent if row.type == "expense" and row.category and row.category.name == "Subscriptions"]
    if sub_rows:
        total = sum((D(row.amount) for row in sub_rows), D(0))
        if total >= D("100"):
            insights.append(
                _insight(
                    key=f"subs:{three_start.isoformat()}:{today.isoformat()}",
                    observation=f"You spent {money_str(total)} on subscriptions in the last three months.",
                    data={"amount": money_str(total), "count": len(sub_rows)},
                    comparison=f"{three_start.strftime('%b %Y')} to {today.strftime('%b %Y')}",
                    explanation=f"{len(sub_rows)} subscription transactions were categorised in this window.",
                    action="Confirm the recurring list and cancel any subscription you no longer use.",
                )
            )

    patterns = spending_patterns(db, user.id, today)
    for item in patterns["items"]:
        if "Weekend" in item["title"]:
            insights.append(
                _insight(
                    key=f"weekend:{today.isoformat()}",
                    observation=item["title"] + ".",
                    data={"detail": item["detail"]},
                    comparison="Last 90 days, weekend days vs weekdays",
                    explanation=item["detail"],
                    action="If weekend plans are the cause, set a weekend cash limit for the rest of the month.",
                )
            )

    status = budget_status(db, user, year, month)
    for item in status["items"]:
        if item["level"] != "over":
            continue
        insights.append(
            _insight(
                key=f"budget:{year}-{month}:{item['category_id']}",
                observation=f"You have exceeded your {item['category_name']} budget.",
                data={"spent": item["spent"], "limit": item["monthly_limit"], "remaining": item["remaining"]},
                comparison=current_label,
                explanation=(
                    f"Spent {item['spent']} against a limit of {item['monthly_limit']}."
                ),
                action="Pause new spending in this category or raise the limit if the plan changed.",
            )
        )

    current_rate = comparison["current"]["savings_rate"]
    previous_rate = comparison["previous"]["savings_rate"]
    delta = comparison["savings_rate_delta"]
    if delta is not None and abs(delta) >= 5 and D(comparison["previous"]["income"]) > 0:
        direction = "improved" if delta > 0 else "fell"
        insights.append(
            _insight(
                key=f"rate:{year}-{month}",
                observation=f"Your savings rate {direction} by {abs(delta)} percentage points.",
                data={"current": current_rate, "previous": previous_rate},
                comparison=f"{current_label} vs {previous_label}",
                explanation=(
                    f"Savings rate is {current_rate}% now and was {previous_rate}% in {previous_label}. "
                    "Savings here means income minus expenses, when income is higher."
                ),
                action="Compare the categories with the biggest change before treating this as a new habit.",
            )
        )

    dismissed = {
        row.insight_key
        for row in db.query(InsightDismissal).filter(InsightDismissal.user_id == user.id).all()
    }
    visible = [item for item in insights if item["key"] not in dismissed]
    # Cap the feed so one noisy category does not flood it.
    return visible[:12]


def dismiss_insight(db: Session, user_id: int, key: str) -> None:
    exists = (
        db.query(InsightDismissal)
        .filter(InsightDismissal.user_id == user_id, InsightDismissal.insight_key == key)
        .first()
    )
    if exists:
        return
    db.add(InsightDismissal(user_id=user_id, insight_key=key[:160]))
    db.commit()
