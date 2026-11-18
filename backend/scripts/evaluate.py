"""Measure categorisation, anomalies, and forecasts on synthetic data.

Writes docs/EVALUATION.md with the numbers this run actually produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sklearn.metrics import precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.categorizer import clean_text, _keyword_match  # noqa: E402
from app.services.forecast import holdout_errors  # noqa: E402

LABELS = [
    ("SWIGGY ORDER 4582", "Food and Dining"),
    ("ZOMATO FOOD", "Food and Dining"),
    ("UBER TRIP 19", "Transportation"),
    ("OLA CAB", "Transportation"),
    ("NETFLIX SUBSCRIPTION", "Subscriptions"),
    ("SPOTIFY PREMIUM", "Subscriptions"),
    ("BESCOM BILL", "Utilities"),
    ("AIRTEL FIBER", "Utilities"),
    ("AMAZON PAYMENTS", "Shopping"),
    ("FLIPKART ORDER", "Shopping"),
    ("HOUSE RENT LANDLORD", "Rent"),
    ("BLINKIT ORDER 88", "Groceries"),
    ("ZEPTO MART", "Groceries"),
    ("EMI HDFC HOME", "EMI and Loan Payments"),
    ("APOLLO PHARMACY", "Healthcare"),
    ("PVR CINEMAS", "Entertainment"),
    ("dinner at the new place", "Food and Dining"),
    ("mystery merchant 77", "Other"),
    ("cash gift from friend", "Other"),
]


def categorizer_scores() -> dict:
    y_true = []
    y_pred = []
    for text, expected in LABELS:
        match = _keyword_match(clean_text(text))
        predicted = match[0] if match else "Other"
        y_true.append(expected)
        y_pred.append(predicted)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    return {
        "rows": len(LABELS),
        "precision": round(float(precision), 3),
        "recall": round(float(recall), 3),
        "f1": round(float(f1), 3),
    }


def anomaly_scores() -> dict:
    """Labelled series: one large food charge is the only true anomaly."""
    import numpy as np

    from app.services.anomaly import _robust_z

    normal = [300.0] * 20
    outlier = 7500.0
    small = 40.0
    values = np.array(normal + [outlier, small])
    flagged = []
    for amount in values:
        median = float(np.median(values))
        score = _robust_z(float(amount), values)
        if amount >= max(median * 3, 1) and score >= 3.5:
            flagged.append(amount)
    true_positive = 1 if outlier in flagged else 0
    false_positive = len([amount for amount in flagged if amount != outlier])
    false_negative = 0 if outlier in flagged else 1
    negatives = len(values) - 1
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0
    recall = true_positive / (true_positive + false_negative)
    false_positive_rate = false_positive / negatives
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "false_positive_rate": round(false_positive_rate, 3),
        "flagged": len(flagged),
    }


def main() -> None:
    categories = categorizer_scores()
    anomalies = anomaly_scores()
    forecast = holdout_errors([10000, 11000, 12000, 13000, 14000, 15000])
    assert forecast is not None
    docs = ROOT.parent / "docs"
    docs.mkdir(exist_ok=True)
    text = f"""# Evaluation

Numbers below were printed by `backend/scripts/evaluate.py` on the synthetic fixtures in that script. They are not estimates of live bank data.

## Transaction categorisation (keyword layer)

- Rows: {categories["rows"]}
- Precision (weighted): {categories["precision"]}
- Recall (weighted): {categories["recall"]}
- F1 (weighted): {categories["f1"]}

`dinner at the new place` has no keyword, so it is counted as Other and lowers recall. `mystery merchant 77` and `cash gift from friend` are correctly left as Other. This score is the keyword layer only. The text model trains after a user corrects at least 30 descriptions.

## Anomaly detection (robust z-score)

Synthetic series: twenty food charges of 300, one charge of 7500 (the labelled anomaly), and one charge of 40 (must stay unflagged).

- Precision: {anomalies["precision"]}
- Recall: {anomalies["recall"]}
- False positive rate: {anomalies["false_positive_rate"]}
- Flagged transactions: {anomalies["flagged"]}

Isolation Forest is used only after a category has 40 expenses. This fixture uses the robust z-score path.

## Forecasting

Rolling one-step errors on the series 10000, 11000, 12000, 13000, 14000, 15000. Training starts once three months exist.

- MAE: {round(forecast["mae"], 2)}
- RMSE: {round(forecast["rmse"], 2)}
- Holdout points: {forecast["points"]}

## AI assistant

Tool execution is covered by `backend/tests/test_intelligence.py` with a fake model client, so it does not spend API tokens. Live tool-selection accuracy is not reported here because it depends on an external model and must not be invented. If `LLM_API_KEY` is empty, the assistant returns a configuration error and does not fabricate an answer.
"""
    (docs / "EVALUATION.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
