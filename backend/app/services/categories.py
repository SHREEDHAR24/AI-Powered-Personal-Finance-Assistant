"""Default categories and lookups that stay inside one user."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants import EXPENSE_CATEGORIES, INCOME_CATEGORIES
from app.models import Category


def seed_categories(db: Session, user_id: int) -> None:
    rows = [(name, "expense") for name in EXPENSE_CATEGORIES] + [
        (name, "income") for name in INCOME_CATEGORIES
    ]
    for name, tx_type in rows:
        db.add(
            Category(
                user_id=user_id,
                name=name,
                transaction_type=tx_type,
                is_system=True,
            )
        )
    db.commit()


def get_user_category(db: Session, user_id: int, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def category_by_name(db: Session, user_id: int, name: str, tx_type: str | None = None) -> Category | None:
    query = db.query(Category).filter(Category.user_id == user_id, Category.name.ilike(name))
    if tx_type:
        query = query.filter(Category.transaction_type == tx_type)
    return query.first()


def other_category(db: Session, user_id: int, tx_type: str) -> Category:
    found = category_by_name(db, user_id, "Other", tx_type)
    if found is None:
        raise HTTPException(status_code=500, detail="Default categories are missing")
    return found
