"""Finance tools and the chat loop.

The model may only call the functions in this file. Each function reads the
signed-in user's rows and returns JSON. The model is not given a database
connection and is not asked to do the arithmetic.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Conversation, Message
from app.money import D, money_str
from app.services.anomaly import detect_anomalies
from app.services.budgets import budget_status
from app.services.categories import category_by_name
from app.services.finance import category_totals, compare_periods, query_transactions, summarise
from app.services.forecast import build_forecast
from app.services.goals import list_goals
from app.services.periods import month_bounds, previous_month, resolve_range
from app.services.reports import monthly_report
from app.services.transactions import list_transactions

TOOL_NAMES = [
    "get_monthly_summary",
    "get_total_income",
    "get_total_expenses",
    "get_category_expenses",
    "compare_monthly_expenses",
    "get_recent_transactions",
    "search_transactions",
    "get_budget_status",
    "get_savings_progress",
    "detect_spending_anomalies",
    "get_expense_forecast",
    "generate_monthly_report",
]


def _range_from_period(period: str | None, start: str | None = None, end: str | None = None):
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    return resolve_range(period or "current_month" if False else (period or "this_month"), start_date, end_date)


def _normalise_period(period: str | None) -> str:
    aliases = {
        None: "this_month",
        "current_month": "this_month",
        "this_month": "this_month",
        "last_month": "last_month",
        "last_3_months": "last_3_months",
        "this_week": "this_week",
        "custom": "custom",
    }
    if period not in aliases:
        raise ValueError("period must be current_month, last_month, last_3_months, this_week, or custom")
    return aliases[period]


def execute_tool(db: Session, user, name: str, arguments: dict) -> dict:
    if name not in TOOL_NAMES:
        return {"error": "That tool is not available."}
    try:
        return _dispatch(db, user, name, arguments or {})
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception:
        return {"error": "The tool could not read your records."}


def _dispatch(db: Session, user, name: str, arguments: dict) -> dict:
    if name == "get_monthly_summary":
        start, end = _period_bounds(arguments)
        rows = query_transactions(db, user.id, start, end)
        return {"period": {"start": start.isoformat(), "end": end.isoformat()}, "currency": user.preferred_currency, **summarise(rows)}
    if name == "get_total_income":
        start, end = _period_bounds(arguments)
        rows = query_transactions(db, user.id, start, end)
        summary = summarise(rows)
        return {"period": {"start": start.isoformat(), "end": end.isoformat()}, "income": summary["income"], "currency": user.preferred_currency}
    if name == "get_total_expenses":
        start, end = _period_bounds(arguments)
        rows = query_transactions(db, user.id, start, end)
        summary = summarise(rows)
        return {"period": {"start": start.isoformat(), "end": end.isoformat()}, "expenses": summary["expenses"], "currency": user.preferred_currency}
    if name == "get_category_expenses":
        category_name = str(arguments.get("category") or "").strip()
        if not category_name:
            raise ValueError("category is required")
        start, end = _period_bounds(arguments)
        category = category_by_name(db, user.id, category_name, "expense")
        rows = query_transactions(db, user.id, start, end)
        if category is None:
            matched = [item for item in category_totals(rows, "expense") if category_name.lower() in item["category"].lower()]
        else:
            matched = [item for item in category_totals(rows, "expense") if item["category_id"] == category.id]
        amount = money_str(sum((D(item["amount"]) for item in matched), D(0)))
        count = sum(item["count"] for item in matched)
        return {
            "category": category.name if category else category_name,
            "found": bool(matched) or category is not None,
            "amount": amount,
            "transaction_count": count,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "currency": user.preferred_currency,
        }
    if name == "compare_monthly_expenses":
        today = date.today()
        year = int(arguments.get("year") or today.year)
        month = int(arguments.get("month") or today.month)
        if not 1 <= month <= 12:
            raise ValueError("month must be 1-12")
        start, end = month_bounds(year, month)
        prev_year, prev_month = previous_month(year, month)
        prev_start, prev_end = month_bounds(prev_year, prev_month)
        comparison = compare_periods(
            query_transactions(db, user.id, start, min(end, today) if (year, month) == (today.year, today.month) else end),
            query_transactions(db, user.id, prev_start, prev_end),
        )
        return {
            "month": f"{year:04d}-{month:02d}",
            "previous_month": f"{prev_year:04d}-{prev_month:02d}",
            "currency": user.preferred_currency,
            **comparison,
        }
    if name == "get_recent_transactions":
        limit = min(int(arguments.get("limit") or 10), 20)
        return list_transactions(db, user.id, limit=limit, sort="date_desc")
    if name == "search_transactions":
        return list_transactions(
            db,
            user.id,
            search=str(arguments.get("query") or ""),
            tx_type=arguments.get("type"),
            limit=min(int(arguments.get("limit") or 20), 30),
        )
    if name == "get_budget_status":
        today = date.today()
        year = int(arguments.get("year") or today.year)
        month = int(arguments.get("month") or today.month)
        return budget_status(db, user, year, month)
    if name == "get_savings_progress":
        goals = list_goals(db, user.id)
        return {"currency": user.preferred_currency, "goals": goals, "count": len(goals)}
    if name == "detect_spending_anomalies":
        return detect_anomalies(db, user.id)
    if name == "get_expense_forecast":
        return build_forecast(db, user.id)
    if name == "generate_monthly_report":
        today = date.today()
        year = int(arguments.get("year") or today.year)
        month = int(arguments.get("month") or today.month)
        report = monthly_report(db, user, year, month)
        report.pop("ai_commentary", None)
        return report
    return {"error": "That tool is not available."}


def _period_bounds(arguments: dict):
    period = _normalise_period(arguments.get("period"))
    start = arguments.get("start_date")
    end = arguments.get("end_date")
    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None
    return resolve_range(period, start_date, end_date)


def tool_specs() -> list[dict]:
    period = {
        "type": "string",
        "enum": ["current_month", "last_month", "last_3_months", "this_week", "custom"],
        "description": "Time window. Use custom with start_date and end_date.",
    }
    return [
        _spec("get_monthly_summary", "Income, expenses, balance, and savings rate for a period.", {"period": period}),
        _spec("get_total_income", "Total income for a period.", {"period": period}),
        _spec("get_total_expenses", "Total expenses for a period.", {"period": period}),
        _spec(
            "get_category_expenses",
            "Spending in one expense category for a period.",
            {"category": {"type": "string"}, "period": period},
            required=["category"],
        ),
        _spec(
            "compare_monthly_expenses",
            "Compare one month with the previous month, including category changes.",
            {"month": {"type": "integer"}, "year": {"type": "integer"}},
        ),
        _spec("get_recent_transactions", "Latest transactions, up to 20.", {"limit": {"type": "integer"}}),
        _spec(
            "search_transactions",
            "Search descriptions and merchants.",
            {"query": {"type": "string"}, "type": {"type": "string", "enum": ["income", "expense"]}, "limit": {"type": "integer"}},
            required=["query"],
        ),
        _spec("get_budget_status", "Budget limits, spend, and alerts for a month.", {"month": {"type": "integer"}, "year": {"type": "integer"}}),
        _spec("get_savings_progress", "Savings goals and recorded contributions.", {}),
        _spec("detect_spending_anomalies", "Expenses that are unusual compared with the user's own history.", {}),
        _spec("get_expense_forecast", "Estimate of next month's spending. An estimate, not a guarantee.", {}),
        _spec("generate_monthly_report", "Calculated monthly report.", {"month": {"type": "integer"}, "year": {"type": "integer"}}),
    ]


def _spec(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return {"type": "function", "function": {"name": name, "description": description, "parameters": schema}}


def _system_prompt(user) -> str:
    return (
        "You are FinMate, a personal finance assistant for one user. "
        f"Their currency is {user.preferred_currency}. Today is {date.today().isoformat()}. "
        "Use the provided tools for every amount, comparison, budget, forecast, or transaction list. "
        "Never invent numbers, never estimate in your head, and never ask for or write SQL. "
        "If a tool returns an error or says data is unavailable, say that plainly. "
        "When you mention a forecast, call it an estimate, not a guaranteed outcome. "
        "Do not label unusual spending as fraud. "
        "Answer in plain language, in short paragraphs. "
        "Do not mention tool names."
    )


def _history(conversation: Conversation) -> list[dict]:
    messages = [{"role": "system", "content": _system_prompt(conversation.user) if False else ""}]
    # Caller replaces the system message. History is user and assistant text only.
    history = []
    for message in conversation.messages[-20:]:
        if message.role in {"user", "assistant"} and message.content:
            history.append({"role": message.role, "content": message.content})
    return history


def iter_reply(db: Session, user, conversation: Conversation, complete=None) -> Iterator[dict]:
    """Yield event dicts: token, tool, error, done."""
    settings = get_settings()
    if complete is None and not settings.llm_configured:
        message = (
            "The assistant is not configured. Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL "
            "in backend/.env and restart the API. FinMate will not invent a reply. "
            "Dashboard, transactions, budgets, and reports still work."
        )
        saved = Message(conversation_id=conversation.id, role="assistant", content=message, tool_trace="[]")
        db.add(saved)
        db.commit()
        db.refresh(saved)
        yield {"event": "error", "message": message}
        yield {"event": "done", "message_id": saved.id, "conversation_id": conversation.id}
        return
    messages = [{"role": "system", "content": _system_prompt(user)}]
    messages.extend(_history(conversation))
    trace = []
    final_text = ""
    try:
        for _round in range(4):
            if complete is None:
                turn = _openai_turn(messages)
            else:
                turn = complete(messages, tool_specs())
            tool_calls = turn.get("tool_calls") or []
            content = turn.get("content") or ""
            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": [
                            {
                                "id": call.get("id") or f"call_{index}",
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": call.get("arguments") if isinstance(call.get("arguments"), str) else json.dumps(call.get("arguments") or {}),
                                },
                            }
                            for index, call in enumerate(tool_calls)
                        ],
                    }
                )
                for index, call in enumerate(tool_calls):
                    raw_args = call.get("arguments") or {}
                    if isinstance(raw_args, str):
                        try:
                            parsed = json.loads(raw_args or "{}")
                        except json.JSONDecodeError:
                            parsed = {}
                    else:
                        parsed = raw_args
                    yield {"event": "tool", "name": call.get("name")}
                    result = execute_tool(db, user, call.get("name") or "", parsed)
                    trace.append({"name": call.get("name"), "arguments": parsed})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id") or f"call_{index}",
                            "content": json.dumps(result),
                        }
                    )
                continue
            final_text = content.strip()
            if not final_text:
                final_text = "I could not answer that from your records."
            # Stream the finished answer in small pieces so the chat UI can render progressively.
            step = 24
            for index in range(0, len(final_text), step):
                yield {"event": "token", "text": final_text[index : index + step]}
            break
        else:
            final_text = "I needed too many lookups and stopped. Ask a narrower question."
            yield {"event": "token", "text": final_text}
    except Exception as exc:
        yield {
            "event": "error",
            "message": f"The language model request failed ({exc.__class__.__name__}). No answer was invented.",
        }
        return

    saved = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=final_text,
        tool_trace=json.dumps(trace),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    yield {"event": "done", "message_id": saved.id, "conversation_id": conversation.id}


def _openai_turn(messages: list[dict]) -> dict:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        messages=messages,
        tools=tool_specs(),
    )
    message = response.choices[0].message
    calls = []
    for call in message.tool_calls or []:
        calls.append({"id": call.id, "name": call.function.name, "arguments": call.function.arguments})
    return {"content": message.content or "", "tool_calls": calls}
