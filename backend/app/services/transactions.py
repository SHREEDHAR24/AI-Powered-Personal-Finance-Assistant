"""Create, search, and change transactions for one user."""

import hashlib

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.constants import PAYMENT_METHODS
from app.models import Category, Transaction
from app.money import D
from app.services.categories import get_user_category
from app.services.categorizer import predict_category, record_correction


def duplicate_hash(user_id: int, day, amount, tx_type: str, description: str) -> str:
    raw = f"{user_id}|{day.isoformat()}|{D(amount)}|{tx_type}|{description.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_method(method: str) -> str:
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Unknown payment method")
    return method


def _ensure_category(db: Session, user_id: int, category_id: int, tx_type: str) -> Category:
    category = get_user_category(db, user_id, category_id)
    if category.transaction_type != tx_type:
        raise HTTPException(status_code=400, detail="Category does not match income or expense")
    return category


def serialize_transaction(row: Transaction) -> dict:
    return {
        "id": row.id,
        "date": row.date.isoformat(),
        "description": row.description,
        "merchant": row.merchant,
        "amount": format(D(row.amount), "f"),
        "type": row.type,
        "category_id": row.category_id,
        "category_name": row.category.name if row.category else None,
        "payment_method": row.payment_method,
        "notes": row.notes,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_transaction(db: Session, user_id: int, payload: dict, source: str = "manual") -> Transaction:
    tx_type = payload["type"]
    prediction = None
    category_id = payload.get("category_id")
    if category_id is None:
        prediction = predict_category(
            db,
            user_id,
            payload["description"],
            payload.get("merchant"),
            tx_type,
            allow_llm=source == "manual",
        )
        category_id = prediction["category_id"]
    _ensure_category(db, user_id, category_id, tx_type)
    row = Transaction(
        user_id=user_id,
        date=payload["date"],
        description=payload["description"].strip(),
        merchant=(payload.get("merchant") or None),
        amount=D(payload["amount"]),
        type=tx_type,
        category_id=category_id,
        payment_method=_validate_method(payload.get("payment_method") or "UPI"),
        notes=payload.get("notes"),
        source=source,
        import_id=payload.get("import_id"),
        duplicate_hash=duplicate_hash(
            user_id, payload["date"], payload["amount"], tx_type, payload["description"]
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.prediction = prediction
    return row


def update_transaction(db: Session, user_id: int, transaction_id: int, payload: dict) -> Transaction:
    row = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.id == transaction_id, Transaction.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    previous_category = row.category_id
    if "description" in payload and payload["description"] is not None:
        row.description = payload["description"].strip()
    if "merchant" in payload:
        row.merchant = payload["merchant"] or None
    if "date" in payload and payload["date"] is not None:
        row.date = payload["date"]
    if "amount" in payload and payload["amount"] is not None:
        row.amount = D(payload["amount"])
    if "type" in payload and payload["type"] is not None:
        row.type = payload["type"]
    if "payment_method" in payload and payload["payment_method"] is not None:
        row.payment_method = _validate_method(payload["payment_method"])
    if "notes" in payload:
        row.notes = payload["notes"]
    if payload.get("category_id"):
        _ensure_category(db, user_id, payload["category_id"], row.type)
        if payload["category_id"] != previous_category:
            record_correction(db, user_id, row.description, previous_category, payload["category_id"])
        row.category_id = payload["category_id"]
    elif row.category and row.category.transaction_type != row.type:
        raise HTTPException(status_code=400, detail="Change the category when you change the type")
    row.duplicate_hash = duplicate_hash(user_id, row.date, row.amount, row.type, row.description)
    db.commit()
    db.refresh(row)
    return row


def delete_transaction(db: Session, user_id: int, transaction_id: int) -> None:
    row = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    db.delete(row)
    db.commit()


def list_transactions(
    db: Session,
    user_id: int,
    *,
    start=None,
    end=None,
    category_id: int | None = None,
    tx_type: str | None = None,
    payment_method: str | None = None,
    min_amount=None,
    max_amount=None,
    search: str | None = None,
    sort: str = "date_desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query = db.query(Transaction).options(joinedload(Transaction.category)).filter(Transaction.user_id == user_id)
    if start:
        query = query.filter(Transaction.date >= start)
    if end:
        query = query.filter(Transaction.date <= end)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if tx_type:
        query = query.filter(Transaction.type == tx_type)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)
    if min_amount is not None:
        query = query.filter(Transaction.amount >= D(min_amount))
    if max_amount is not None:
        query = query.filter(Transaction.amount <= D(max_amount))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            Transaction.description.ilike(like) | Transaction.merchant.ilike(like) | Transaction.notes.ilike(like)
        )
    total = query.count()
    if sort == "amount_asc":
        query = query.order_by(Transaction.amount.asc(), Transaction.id.desc())
    elif sort == "amount_desc":
        query = query.order_by(Transaction.amount.desc(), Transaction.id.desc())
    elif sort == "date_asc":
        query = query.order_by(Transaction.date.asc(), Transaction.id.asc())
    else:
        query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    rows = query.offset(offset).limit(min(limit, 200)).all()
    return {"total": total, "items": [serialize_transaction(row) for row in rows]}
