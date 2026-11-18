"""Find charges that repeat with a stable amount and a weekly, monthly, or quarterly gap."""

import json
import re
import statistics
from collections import defaultdict
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import RecurringItem, Transaction
from app.money import D, money_str
from app.services.categorizer import clean_text

STOP_WORDS = {"upi", "neft", "imps", "ref", "txn", "payment", "pay", "to", "from", "inr"}


def fingerprint(description: str) -> str:
    text = clean_text(description)
    words = [word for word in text.split() if word not in STOP_WORDS and not word.isdigit()]
    return " ".join(words)[:160]


def _cadence(gaps: list[int]) -> str | None:
    if len(gaps) < 2:
        return None
    median = statistics.median(gaps)
    if 6 <= median <= 8:
        return "weekly"
    if 25 <= median <= 35:
        return "monthly"
    if 85 <= median <= 100:
        return "quarterly"
    return None


def _stable_amount(amounts: list) -> bool:
    median = statistics.median(amounts)
    if median == 0:
        return False
    spread = (max(amounts) - min(amounts)) / median
    return spread <= 0.1


def detect_recurring(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.type == "expense")
        .order_by(Transaction.date.asc())
        .all()
    )
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for row in rows:
        key = fingerprint(row.description)
        if len(key) < 3:
            continue
        groups[key].append(row)

    known = {
        item.fingerprint: item
        for item in db.query(RecurringItem).filter(RecurringItem.user_id == user_id).all()
    }
    for key, items in groups.items():
        if len(items) < 3:
            continue
        amounts = [float(D(item.amount)) for item in items]
        if not _stable_amount(amounts):
            continue
        dates = sorted({item.date for item in items})
        if len(dates) < 3:
            continue
        gaps = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
        cadence = _cadence(gaps)
        if cadence is None:
            continue
        median_gap = statistics.median(gaps)
        stdev = statistics.pstdev(gaps) if len(gaps) > 1 else 0
        stable_gap = stdev <= 0.25 * median_gap
        next_date = dates[-1] + timedelta(days=int(round(median_gap))) if stable_gap else None
        label = re.sub(r"\s+", " ", items[-1].description).strip()[:160]
        existing = known.get(key)
        if existing and existing.status == "rejected":
            continue
        if existing is None:
            existing = RecurringItem(
                user_id=user_id,
                fingerprint=key,
                display_name=label,
                status="suggested",
                estimated_amount=D(statistics.median(amounts)),
                cadence=cadence,
                previous_dates=json.dumps([day.isoformat() for day in dates]),
                next_date=next_date,
            )
            db.add(existing)
            known[key] = existing
        else:
            existing.display_name = label
            existing.estimated_amount = D(statistics.median(amounts))
            existing.cadence = cadence
            existing.previous_dates = json.dumps([day.isoformat() for day in dates])
            existing.next_date = next_date
    db.commit()
    items = (
        db.query(RecurringItem)
        .filter(RecurringItem.user_id == user_id, RecurringItem.status != "rejected")
        .order_by(RecurringItem.estimated_amount.desc())
        .all()
    )
    return [_serialize(item) for item in items]


def _serialize(item: RecurringItem) -> dict:
    try:
        dates = json.loads(item.previous_dates or "[]")
    except json.JSONDecodeError:
        dates = []
    return {
        "id": item.id,
        "name": item.display_name,
        "status": item.status,
        "estimated_monthly_cost": money_str(item.estimated_amount) if item.cadence == "monthly" else None,
        "estimated_amount": money_str(item.estimated_amount),
        "cadence": item.cadence,
        "previous_dates": dates,
        "next_expected_date": item.next_date.isoformat() if item.next_date else None,
    }


def set_status(db: Session, user_id: int, item_id: int, status: str) -> dict:
    item = db.query(RecurringItem).filter(RecurringItem.id == item_id, RecurringItem.user_id == user_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Recurring item not found")
    item.status = status
    db.commit()
    db.refresh(item)
    return _serialize(item)
