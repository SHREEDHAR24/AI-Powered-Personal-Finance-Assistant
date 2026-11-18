"""CSV bank-statement import. Nothing is saved until the user confirms."""

from __future__ import annotations

import io
import json
import re
import uuid
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import PREVIEW_DIR
from app.models import ImportRecord, Transaction
from app.money import D
from app.services.categories import get_user_category
from app.services.categorizer import predict_category
from app.services.transactions import duplicate_hash

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
PREVIEW_HOURS = 12

HEADER_HINTS = {
    "date": ["date", "txn date", "transaction date", "value date", "posted"],
    "description": ["description", "narration", "particulars", "details", "remark"],
    "debit": ["debit", "withdrawal", "dr", "money out"],
    "credit": ["credit", "deposit", "cr", "money in"],
    "amount": ["amount", "txn amount", "transaction amount"],
    "type": ["type", "dr/cr", "cr/dr"],
    "balance": ["balance", "closing balance"],
    "merchant": ["merchant", "payee"],
    "notes": ["notes", "note"],
    "payment_method": ["payment method", "mode", "channel"],
}


def _suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    mapping = {key: None for key in HEADER_HINTS}
    used = set()
    for field, hints in HEADER_HINTS.items():
        for column in columns:
            if column in used:
                continue
            lowered = column.strip().lower()
            if lowered in hints or any(hint == lowered for hint in hints):
                mapping[field] = column
                used.add(column)
                break
    return mapping


def _clean_amount(value) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "-"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "")
    text = text.replace("inr", "").replace(" ", "")
    text = text.strip("()")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if negative:
        amount = -amount
    return D(abs(amount)) if amount != 0 else None


def _clean_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    parsed = pd.to_datetime(str(value).strip(), dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(str(value).strip(), dayfirst=False, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _clean_description(value) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def analyse_csv(file_name: str, content: bytes, user_id: int) -> dict:
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="CSV files must be 5 MB or smaller")
    if not file_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read that CSV") from exc
    if frame.empty:
        raise HTTPException(status_code=400, detail="The CSV has no rows")
    if len(frame) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"Imports are limited to {MAX_ROWS} rows")
    columns = [str(column) for column in frame.columns]
    preview_id = uuid.uuid4().hex
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "user_id": user_id,
        "file_name": file_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "columns": columns,
        "rows": frame.fillna("").astype(str).to_dict(orient="records"),
    }
    (PREVIEW_DIR / f"{preview_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    sample = payload["rows"][:5]
    return {
        "preview_id": preview_id,
        "file_name": file_name,
        "columns": columns,
        "row_count": len(payload["rows"]),
        "sample_rows": sample,
        "suggested_mapping": _suggest_mapping(columns),
    }


def _load_preview(preview_id: str, user_id: int) -> dict:
    path = PREVIEW_DIR / f"{preview_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Import preview expired. Upload the file again.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Import preview expired. Upload the file again.")
    created = datetime.fromisoformat(payload["created_at"])
    if datetime.now(timezone.utc) - created > timedelta(hours=PREVIEW_HOURS):
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Import preview expired. Upload the file again.")
    return payload


def build_preview(db: Session, user_id: int, preview_id: str, mapping: dict) -> dict:
    payload = _load_preview(preview_id, user_id)
    columns = set(payload["columns"])
    for field, column in mapping.items():
        if column and column not in columns:
            raise HTTPException(status_code=400, detail=f"Column '{column}' is not in the file")
    if not mapping.get("date") or not mapping.get("description"):
        raise HTTPException(status_code=400, detail="Map a date column and a description column")
    if not (mapping.get("debit") or mapping.get("credit") or mapping.get("amount")):
        raise HTTPException(status_code=400, detail="Map a debit, credit, or amount column")

    existing = {
        row[0]
        for row in db.query(Transaction.duplicate_hash).filter(Transaction.user_id == user_id).all()
    }
    seen_in_file = set()
    processed = []
    invalid = []
    duplicate_count = 0
    for index, raw in enumerate(payload["rows"], start=1):
        result = _process_row(db, user_id, index, raw, mapping, existing, seen_in_file)
        if result["status"] == "invalid":
            invalid.append(result)
        else:
            if result["status"] == "duplicate":
                duplicate_count += 1
            processed.append(result)

    preview_path = PREVIEW_DIR / f"{preview_id}.preview.json"
    preview_path.write_text(
        json.dumps(
            {"mapping": mapping, "rows": processed, "invalid_rows": len(invalid)},
            default=str,
        ),
        encoding="utf-8",
    )
    ready = [row for row in processed if row["status"] == "ready"]
    return {
        "preview_id": preview_id,
        "file_name": payload["file_name"],
        "total_rows": len(payload["rows"]),
        "ready_rows": len(ready),
        "duplicate_rows": duplicate_count,
        "invalid_rows": len(invalid),
        "rows": processed,
        "invalid": invalid,
    }


def _process_row(db, user_id, index, raw, mapping, existing, seen_in_file) -> dict:
    day = _clean_date(raw.get(mapping["date"]))
    description = _clean_description(raw.get(mapping["description"]))
    if day is None or not description:
        return {"index": index, "status": "invalid", "reason": "Missing date or description", "raw": raw}

    debit = _clean_amount(raw.get(mapping["debit"])) if mapping.get("debit") else None
    credit = _clean_amount(raw.get(mapping["credit"])) if mapping.get("credit") else None
    amount = None
    tx_type = None
    if debit and (not credit or debit >= credit):
        amount, tx_type = debit, "expense"
    elif credit:
        amount, tx_type = credit, "income"
    elif mapping.get("amount"):
        parsed = _clean_amount(raw.get(mapping["amount"]))
        if parsed is None:
            return {"index": index, "status": "invalid", "reason": "Amount is empty or not a number", "raw": raw}
        tx_type = "expense"
        if mapping.get("type"):
            marker = str(raw.get(mapping["type"], "")).strip().lower()
            if marker in {"cr", "credit", "income", "deposit"}:
                tx_type = "income"
            elif marker in {"dr", "debit", "expense", "withdrawal"}:
                tx_type = "expense"
        amount = parsed
    if amount is None or tx_type is None:
        return {"index": index, "status": "invalid", "reason": "No debit or credit amount", "raw": raw}

    merchant = _clean_description(raw.get(mapping["merchant"])) if mapping.get("merchant") else ""
    notes = _clean_description(raw.get(mapping["notes"])) if mapping.get("notes") else ""
    method = "Other"
    if mapping.get("payment_method"):
        candidate = _clean_description(raw.get(mapping["payment_method"]))
        method = candidate if candidate else "Other"
    prediction = predict_category(db, user_id, description, merchant or None, tx_type, allow_llm=False)
    digest = duplicate_hash(user_id, day, amount, tx_type, description)
    status = "ready"
    reason = None
    if digest in existing or digest in seen_in_file:
        status = "duplicate"
        reason = "Same date, amount, type, and description already exist"
    seen_in_file.add(digest)
    return {
        "index": index,
        "status": status,
        "reason": reason,
        "date": day.isoformat(),
        "description": description,
        "merchant": merchant or None,
        "amount": format(amount, "f"),
        "type": tx_type,
        "payment_method": method if method in {
            "UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Wallet", "Other"
        } else "Other",
        "notes": notes or None,
        "category_id": prediction["category_id"],
        "category_name": prediction["category_name"],
        "confidence": prediction["confidence"],
        "category_source": prediction["source"],
        "duplicate_hash": digest,
    }


def commit_preview(db: Session, user_id: int, preview_id: str, overrides: dict[int, dict]) -> dict:
    payload = _load_preview(preview_id, user_id)
    preview_path = PREVIEW_DIR / f"{preview_id}.preview.json"
    if not preview_path.exists():
        raise HTTPException(status_code=400, detail="Review the column mapping before saving")
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    record = ImportRecord(
        user_id=user_id,
        file_name=payload["file_name"][:255],
        total_rows=len(payload["rows"]),
        successful_rows=0,
        duplicate_rows=0,
        invalid_rows=int(preview.get("invalid_rows") or 0),
    )
    db.add(record)
    db.flush()
    saved = 0
    duplicates = 0
    for row in preview["rows"]:
        if row["status"] == "duplicate":
            duplicates += 1
            continue
        if row["status"] != "ready":
            continue
        choice = overrides.get(row["index"], {})
        if choice.get("include") is False:
            continue
        category_id = int(choice.get("category_id") or row["category_id"])
        category = get_user_category(db, user_id, category_id)
        if category.transaction_type != row["type"]:
            raise HTTPException(status_code=400, detail="A chosen category does not match the row type")
        db.add(
            Transaction(
                user_id=user_id,
                date=date_cls.fromisoformat(row["date"]),
                description=row["description"],
                merchant=row["merchant"],
                amount=D(row["amount"]),
                type=row["type"],
                category_id=category_id,
                payment_method=row["payment_method"],
                notes=row["notes"],
                source="csv",
                import_id=record.id,
                duplicate_hash=row["duplicate_hash"],
            )
        )
        saved += 1
    record.successful_rows = saved
    record.duplicate_rows = duplicates
    db.commit()
    (PREVIEW_DIR / f"{preview_id}.json").unlink(missing_ok=True)
    preview_path.unlink(missing_ok=True)
    return {
        "import_id": record.id,
        "file_name": record.file_name,
        "total_rows": record.total_rows,
        "successful_rows": record.successful_rows,
        "duplicate_rows": record.duplicate_rows,
        "invalid_rows": record.invalid_rows,
    }


def list_imports(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(ImportRecord)
        .filter(ImportRecord.user_id == user_id)
        .order_by(ImportRecord.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": row.id,
            "file_name": row.file_name,
            "import_date": row.import_date.isoformat() if row.import_date else None,
            "total_rows": row.total_rows,
            "successful_rows": row.successful_rows,
            "duplicate_rows": row.duplicate_rows,
            "invalid_rows": row.invalid_rows,
        }
        for row in rows
    ]
