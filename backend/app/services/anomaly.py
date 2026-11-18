"""Unusual spending. Statistical rules first, Isolation Forest when a category has enough history.

These are review flags, not fraud labels.
"""

from collections import defaultdict

import numpy as np
from sqlalchemy.orm import Session, joinedload

from app.models import Transaction
from app.money import D, money_str


def _robust_z(amount: float, values: np.ndarray) -> float:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    # A zero MAD means the typical spend barely varies. Use a small band around
    # the median so one large charge still stands out.
    if mad == 0:
        mad = max(abs(median) * 0.05, 1.0)
    return 0.6745 * (amount - median) / mad


def detect_anomalies(db: Session, user_id: int, limit: int = 20) -> dict:
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.user_id == user_id, Transaction.type == "expense")
        .all()
    )
    grouped: dict[int, list[Transaction]] = defaultdict(list)
    for row in rows:
        grouped[row.category_id].append(row)

    flags = []
    for category_rows in grouped.values():
        if len(category_rows) < 8:
            continue
        values = np.array([float(D(row.amount)) for row in category_rows], dtype=float)
        median = float(np.median(values))
        if median <= 0:
            continue
        use_forest = len(category_rows) >= 40
        forest_scores = None
        if use_forest:
            from sklearn.ensemble import IsolationForest

            weekend = np.array([1.0 if row.date.weekday() >= 5 else 0.0 for row in category_rows])
            ratio = values / median
            features = np.column_stack([values, ratio, weekend])
            model = IsolationForest(random_state=42, contamination=0.08)
            model.fit(features)
            forest_scores = -model.score_samples(features)

        for index, row in enumerate(category_rows):
            amount = float(D(row.amount))
            score = _robust_z(amount, values)
            times = amount / median if median else 0
            # Ignore tiny purchases even if they are relatively odd.
            if amount < max(median * 3, 1):
                continue
            flagged = False
            method = "robust_z"
            if use_forest and forest_scores is not None:
                method = "isolation_forest"
                # Flag only if the forest score is in the top of this category and the spend is large.
                cutoff = float(np.quantile(forest_scores, 0.92))
                flagged = forest_scores[index] >= cutoff and score >= 2.5
                display_score = round(float(forest_scores[index]), 3)
            else:
                flagged = score >= 3.5
                display_score = round(score, 2)
            if not flagged:
                continue
            category_name = row.category.name if row.category else "Other"
            flags.append(
                {
                    "transaction_id": row.id,
                    "date": row.date.isoformat(),
                    "description": row.description,
                    "category": category_name,
                    "amount": money_str(amount),
                    "typical_amount": money_str(median),
                    "times_typical": round(times, 1),
                    "score": display_score,
                    "method": method,
                    "reason": (
                        f"This {category_name} expense is about {times:.1f} times your usual "
                        f"{category_name} spend of {money_str(median)}. It is only a prompt to review that charge."
                    ),
                }
            )
    flags.sort(key=lambda item: item["times_typical"], reverse=True)
    return {"count": len(flags[:limit]), "items": flags[:limit]}
