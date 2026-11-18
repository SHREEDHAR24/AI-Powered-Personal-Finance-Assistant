# Evaluation

Numbers below were printed by `backend/scripts/evaluate.py` on the synthetic fixtures in that script. They are not estimates of live bank data.

## Transaction categorisation (keyword layer)

- Rows: 19
- Precision (weighted): 0.965
- Recall (weighted): 0.947
- F1 (weighted): 0.947

`dinner at the new place` has no keyword, so it is counted as Other and lowers recall. `mystery merchant 77` and `cash gift from friend` are correctly left as Other. This score is the keyword layer only. The text model trains after a user corrects at least 30 descriptions.

## Anomaly detection (robust z-score)

Synthetic series: twenty food charges of 300, one charge of 7500 (the labelled anomaly), and one charge of 40 (must stay unflagged).

- Precision: 1.0
- Recall: 1.0
- False positive rate: 0.0
- Flagged transactions: 1

Isolation Forest is used only after a category has 40 expenses. This fixture uses the robust z-score path.

## Forecasting

Rolling one-step errors on the series 10000, 11000, 12000, 13000, 14000, 15000. Training starts once three months exist.

- MAE: 2073.6
- RMSE: 2074.82
- Holdout points: 3

## AI assistant

Tool execution is covered by `backend/tests/test_intelligence.py` with a fake model client, so it does not spend API tokens. Live tool-selection accuracy is not reported here because it depends on an external model and must not be invented. If `LLM_API_KEY` is empty, the assistant returns a configuration error and does not fabricate an answer.
