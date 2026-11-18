"""Synthetic Indian household ledger for demos. Rows are tagged source=demo."""

import random
from datetime import date

from sqlalchemy.orm import Session

from app.models import Transaction
from app.money import D
from app.services.categories import category_by_name
from app.services.transactions import duplicate_hash


def load_demo(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    clear_demo(db, user_id)
    rng = random.Random(42)
    # Six months ending this month.
    months = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()

    def add(year, month, day, description, amount, tx_type, category_name, merchant=None):
        category = category_by_name(db, user_id, category_name, tx_type)
        if category is None:
            return
        booked = date(year, month, min(day, 28))
        if booked > today:
            return
        db.add(
            Transaction(
                user_id=user_id,
                date=booked,
                description=description,
                merchant=merchant,
                amount=D(amount),
                type=tx_type,
                category_id=category.id,
                payment_method="UPI" if tx_type == "expense" else "Net Banking",
                notes="Sample data",
                source="demo",
                duplicate_hash=duplicate_hash(user_id, booked, amount, tx_type, description),
            )
        )

    count = 0
    for year, month in months:
        add(year, month, 1, "SALARY ACME PAYROLL", 82000, "income", "Salary", "Acme")
        add(year, month, 3, "HOUSE RENT LANDLORD", 22000, "expense", "Rent", "Landlord")
        add(year, month, 2, "GYM MEMBERSHIP", 1500, "expense", "Personal Care", "Gym")
        add(year, month, 8, "BESCOM ELECTRICITY BILL", 1600 + (month % 3) * 80, "expense", "Utilities", "BESCOM")
        add(year, month, 8, "AIRTEL FIBER BROADBAND", 999, "expense", "Utilities", "Airtel")
        add(year, month, 15, "NETFLIX SUBSCRIPTION", 649, "expense", "Subscriptions", "Netflix")
        add(year, month, 15, "SPOTIFY PREMIUM", 119, "expense", "Subscriptions", "Spotify")
        for slot in range(4):
            add(year, month, 5 + slot * 6, f"BLINKIT ORDER {1000 + slot}", rng.randint(420, 980), "expense", "Groceries", "Blinkit")
        for slot in range(6):
            add(year, month, 4 + slot * 4, f"SWIGGY ORDER {2000 + slot}", rng.randint(220, 540), "expense", "Food and Dining", "Swiggy")
        for slot in range(3):
            add(year, month, 6 + slot * 7, f"UBER TRIP {3000 + slot}", rng.randint(120, 340), "expense", "Transportation", "Uber")
        add(year, month, 18, "AMAZON PAYMENTS", rng.randint(900, 2400), "expense", "Shopping", "Amazon")
        count += 1
    # One deliberate outlier in the latest month that has already started.
    latest_year, latest_month = months[-1]
    add(latest_year, latest_month, min(today.day, 12), "SWIGGY ORDER 9999", 7500, "expense", "Food and Dining", "Swiggy")
    db.commit()
    total = db.query(Transaction).filter(Transaction.user_id == user_id, Transaction.source == "demo").count()
    return {"loaded": total, "months": len(months)}


def clear_demo(db: Session, user_id: int) -> dict:
    deleted = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.source == "demo")
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}
