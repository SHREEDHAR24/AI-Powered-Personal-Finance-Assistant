# Development status

Updated after the automated test run in this workspace.

## Completed

- Accounts: register, login, logout, profile, currency symbol, alert thresholds, account deletion
- Default and custom categories, user categorisation rules
- Transactions: create, edit, delete, search, filter, sort
- Dashboard cards and charts calculated from transactions
- CSV import: column mapping, cleaning, duplicates, preview, confirm, history
- Keyword categorisation, with a text model after 30 corrections
- Monthly budgets, alerts, and “use last month” suggestions
- Savings goals and recorded contributions
- Analytics, month comparison, unusual expenses, forecast (needs three months)
- Insight cards with dismiss, recurring-charge review
- PDF and CSV reports, with an optional AI paragraph only when a key is set
- Assistant tools and streaming chat. Without `LLM_API_KEY` the chat explains that it is not configured
- Sample ledger in Settings
- Pytest suite: 15 passed
- `docs/EVALUATION.md` written by `backend/scripts/evaluate.py`
- Dockerfiles and compose file

## Pending

- A live language-model tool-selection score. That needs an API key and must be measured, not guessed
- Postgres in a deployed environment. The app reads `DATABASE_URL`, but the Postgres driver is not installed yet
- Running `docker compose` on this machine. Docker is not installed here

## Known limits

- Currency changes the symbol only. Amounts are not converted
- Forecasts lag a steadily rising series. The measured error is in `docs/EVALUATION.md`
- Isolation Forest runs only after a category has 40 expenses. Smaller histories use a robust z-score
- CSV import does not send rows to an external model

## Setup

See `README.md`. API on port 8000, web app on port 3000.

## Next tasks

- Deploy the API and set `API_PROXY_TARGET` on the frontend
- Add `psycopg` when moving the database to Postgres
- If an LLM key is added, record tool-selection accuracy from a fixed question list
