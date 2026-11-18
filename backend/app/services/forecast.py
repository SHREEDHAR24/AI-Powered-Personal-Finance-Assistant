"""Expense estimates from monthly history.

A forecast is only returned when at least three separate months exist.
Figures are estimates, not promises.
"""

from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.models import Transaction
from app.money import D, money_str


def _blend(values: list[float]) -> float:
    window = values[-3:]
    moving = sum(window) / len(window)
    smoothed = values[0]
    for value in values[1:]:
        smoothed = 0.4 * value + 0.6 * smoothed
    return 0.5 * moving + 0.5 * smoothed


def _monthly_maps(rows: list[Transaction]):
    expense: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    income: dict[str, float] = defaultdict(float)
    for row in rows:
        key = row.date.strftime("%Y-%m")
        amount = float(D(row.amount))
        if row.type == "income":
            income[key] += amount
        else:
            name = row.category.name if row.category else "Other"
            expense[key][name] += amount
    return expense, income


def build_forecast(db: Session, user_id: int) -> dict:
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.user_id == user_id)
        .all()
    )
    expense, income = _monthly_maps(rows)
    months = sorted(set(expense) | set(income))
    if len(months) < 3:
        return {
            "available": False,
            "reason": "At least three different months of transactions are needed before FinMate can estimate next month.",
            "months_available": len(months),
        }
    totals = [sum(expense[month].values()) for month in months]
    estimate = _blend(totals)
    category_names = sorted({name for month in expense.values() for name in month})
    categories = []
    for name in category_names:
        series = [expense[month].get(name, 0.0) for month in months]
        if sum(1 for value in series if value > 0) < 2 and sum(series) == 0:
            continue
        # Skip categories that barely appear.
        if sum(1 for value in series if value > 0) < 2:
            continue
        categories.append({"category": name, "amount": money_str(max(_blend(series), 0))})
    categories.sort(key=lambda item: float(item["amount"]), reverse=True)
    income_series = [income.get(month, 0.0) for month in months]
    income_estimate = _blend(income_series) if any(income_series) else 0
    savings_estimate = income_estimate - estimate
    return {
        "available": True,
        "method": "Average of a 3-month moving average and exponential smoothing",
        "history_months": months,
        "next_month_expenses": money_str(max(estimate, 0)),
        "next_month_income": money_str(max(income_estimate, 0)),
        "expected_savings": money_str(savings_estimate),
        "categories": categories[:12],
        "note": "This is an estimate from your history, not a guaranteed outcome.",
    }


def holdout_errors(monthly_totals: list[float]) -> dict | None:
    """Rolling one-month-ahead MAE and RMSE. Used by the evaluation script."""
    if len(monthly_totals) < 4:
        return None
    errors = []
    for index in range(3, len(monthly_totals)):
        predicted = _blend(monthly_totals[:index])
        errors.append(predicted - monthly_totals[index])
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = (sum(error * error for error in errors) / len(errors)) ** 0.5
    return {"mae": mae, "rmse": rmse, "points": len(errors)}
