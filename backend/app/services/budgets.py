"""Monthly category budgets and threshold alerts."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import Budget, Transaction
from app.money import D, money_str, pct
from app.services.categories import get_user_category
from app.services.periods import month_bounds


def _spent(db: Session, user_id: int, category_id: int, year: int, month: int):
    start, end = month_bounds(year, month)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.type == "expense",
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )
    return sum((D(row.amount) for row in rows), D(0))


def budget_status(db: Session, user, year: int, month: int) -> dict:
    rows = (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(Budget.user_id == user.id, Budget.year == year, Budget.month == month)
        .all()
    )
    items = []
    total_limit = D(0)
    total_spent = D(0)
    alerts = []
    for row in rows:
        spent = _spent(db, user.id, row.category_id, year, month)
        limit = D(row.monthly_limit)
        ratio = pct(spent, limit)
        level = "ok"
        if ratio is not None and ratio >= 100:
            level = "over"
        elif ratio is not None and ratio >= user.alert_critical_pct:
            level = "critical"
        elif ratio is not None and ratio >= user.alert_warn_pct:
            level = "warn"
        remaining = limit - spent
        item = {
            "id": row.id,
            "category_id": row.category_id,
            "category_name": row.category.name if row.category else "Category",
            "monthly_limit": money_str(limit),
            "spent": money_str(spent),
            "remaining": money_str(remaining),
            "utilisation": ratio,
            "level": level,
            "month": month,
            "year": year,
        }
        items.append(item)
        total_limit += limit
        total_spent += spent
        if level == "warn":
            alerts.append(
                f"You have used {ratio}% of your {item['category_name']} budget, with {money_str(remaining)} remaining."
            )
        elif level == "critical":
            alerts.append(
                f"You have used {ratio}% of your {item['category_name']} budget, with {money_str(remaining)} remaining."
            )
        elif level == "over":
            alerts.append(
                f"You are over your {item['category_name']} budget by {money_str(abs(remaining))}."
            )
    items.sort(key=lambda item: item["utilisation"] or 0, reverse=True)
    return {
        "month": month,
        "year": year,
        "items": items,
        "total_limit": money_str(total_limit),
        "total_spent": money_str(total_spent),
        "utilisation": pct(total_spent, total_limit),
        "alerts": alerts,
        "warn_pct": user.alert_warn_pct,
        "critical_pct": user.alert_critical_pct,
    }


def create_budget(db: Session, user_id: int, category_id: int, limit, month: int, year: int) -> Budget:
    category = get_user_category(db, user_id, category_id)
    if category.transaction_type != "expense":
        raise HTTPException(status_code=400, detail="Budgets apply to expense categories")
    existing = (
        db.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.month == month,
            Budget.year == year,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="That category already has a budget for this month")
    row = Budget(
        user_id=user_id,
        category_id=category_id,
        monthly_limit=D(limit),
        month=month,
        year=year,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_budget(db: Session, user_id: int, budget_id: int, limit) -> Budget:
    row = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    row.monthly_limit = D(limit)
    db.commit()
    db.refresh(row)
    return row


def delete_budget(db: Session, user_id: int, budget_id: int) -> None:
    row = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(row)
    db.commit()


def suggest_budgets(db: Session, user, year: int, month: int) -> dict:
    """Create budgets from the previous month's actual spend where none exist yet."""
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    start, end = month_bounds(prev_year, prev_month)
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.type == "expense",
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )
    totals: dict[int, D] = {}
    for row in rows:
        totals[row.category_id] = totals.get(row.category_id, D(0)) + D(row.amount)
    created = 0
    for category_id, amount in totals.items():
        if amount <= 0:
            continue
        exists = (
            db.query(Budget)
            .filter(
                Budget.user_id == user.id,
                Budget.category_id == category_id,
                Budget.month == month,
                Budget.year == year,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            Budget(
                user_id=user.id,
                category_id=category_id,
                monthly_limit=amount,
                month=month,
                year=year,
            )
        )
        created += 1
    db.commit()
    return {"created": created, "status": budget_status(db, user, year, month)}


def current_budget_month(today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    return today.year, today.month
