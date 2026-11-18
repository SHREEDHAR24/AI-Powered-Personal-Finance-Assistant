# FinMate

FinMate is a personal finance app. It stores transactions, imports bank CSVs, tracks budgets and savings goals, and calculates spending analytics in Python. An assistant can answer questions by calling those same calculations. It does not invent amounts, and it does not talk to your bank.

## What works without an API key

- Accounts, with passwords hashed by bcrypt and a session cookie
- Transactions: add, edit, delete, search, filter, sort
- Dashboard cards and charts from those transactions
- CSV import with column mapping, cleaning, duplicate detection, and a confirm step
- Keyword categorisation, your own rules, and a text model after 30 corrections
- Monthly budgets and alerts
- Savings goals from contributions you record
- Comparisons, unusual-spend flags, and a forecast once three months exist
- Insight cards, recurring-charge review, PDF and CSV reports

The assistant and the optional AI paragraph in a report need `LLM_API_KEY`. If it is missing, FinMate says so. It does not fake a chat reply.

## Run it locally

Requirements: Python 3.12 or 3.13, Node.js 20+.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
copy .env.example backend\.env
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The Next.js app proxies `/api` to the API on port 8000.

If port 8000 is already taken, start the API on another port and set `API_PROXY_TARGET` before `npm run dev`:

```bash
.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8001
```

```bash
set API_PROXY_TARGET=http://127.0.0.1:8001
npm run dev
```

On macOS or Linux, create the virtualenv the usual way and run `uvicorn` from `.venv/bin`.

### Try it

1. Create an account.
2. Open Settings and choose **Load sample finances**, or import `sample_data/sample_statement.csv`.
3. The dashboard, budgets, analytics, insights, and reports then use those rows.

Sample rows are tagged `demo` and can be removed without touching transactions you added yourself.

### Optional language model

In `backend/.env`:

```
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

Any OpenAI-compatible chat API works. Set `LLM_BASE_URL` to that provider. Restart the API after changing the file.

`LLM_CATEGORIZE_FALLBACK=true` lets a single manual transaction ask the model for a category when rules and keywords miss. The answer must be one of your categories. CSV import never sends rows to the model.

## Tests and measured scores

```bash
.venv\Scripts\python -m pytest backend/tests -q
.venv\Scripts\python backend/scripts/evaluate.py
```

`docs/EVALUATION.md` is rewritten by the evaluation script. The figures in that file come from the synthetic fixtures, not from a guess.

## Docker

Docker is optional. From the project root, with Docker installed:

```bash
docker compose up --build
```

The API is on port 8000 and the web app on port 3000. SQLite data sits in the `finmate-data` volume.

## Deploy

- Frontend: Vercel. Set `API_PROXY_TARGET` to the public API URL.
- API: Render (or similar). Set `JWT_SECRET`, and set `DATABASE_URL` to Postgres when you leave SQLite (`postgresql+psycopg://...`). The models use SQLAlchemy, so the URL is the switch. Add a Postgres driver such as `psycopg` before using that URL.
- Do not commit `backend/.env`.

## Layout

- `backend/app/api` HTTP routes, all scoped to the signed-in user
- `backend/app/services/finance.py` shared money calculations
- `backend/app/services/assistant.py` the only functions the model may call
- `frontend/src/app` pages

## Privacy

FinMate does not ask for bank passwords, OTPs, UPI PINs, or card CVVs, and it does not connect to a bank. Deleting the account removes that user's rows.
