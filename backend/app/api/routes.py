"""HTTP routes for FinMate. Every financial query is scoped to the signed-in user."""

import json
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.constants import CURRENCIES, PAYMENT_METHODS
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Category, CategoryRule, Conversation, Message, User
from app.schemas import (
    BudgetIn,
    BudgetPatch,
    CategoryIn,
    ChatIn,
    CommitIn,
    ContributionIn,
    ConversationIn,
    DismissIn,
    GoalIn,
    GoalPatch,
    LoginIn,
    MappingIn,
    ProfileIn,
    RegisterIn,
    RuleIn,
    TransactionIn,
    TransactionPatch,
)
from app.services.anomaly import detect_anomalies
from app.services.assistant import iter_reply
from app.services.budgets import budget_status, create_budget, delete_budget, suggest_budgets, update_budget
from app.services.categories import get_user_category, seed_categories
from app.services.demo import clear_demo, load_demo
from app.services.finance import (
    average_daily_spend,
    category_totals,
    compare_periods,
    largest_expense,
    monthly_series,
    query_transactions,
    summarise,
    weekly_spending,
)
from app.services.forecast import build_forecast
from app.services.goals import add_contribution, create_goal, delete_contribution, delete_goal, list_goals, update_goal
from app.services.importer import analyse_csv, build_preview, commit_preview, list_imports
from app.services.insights import dismiss_insight, generate_insights
from app.services.patterns import spending_patterns
from app.services.periods import month_bounds, previous_month, resolve_range
from app.services.recurring import detect_recurring, set_status
from app.services.reports import maybe_ai_commentary, monthly_report, report_csv, report_pdf, yearly_report
from app.services.transactions import create_transaction, delete_transaction, list_transactions, serialize_transaction, update_transaction

router = APIRouter()
settings = get_settings()


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "preferred_currency": user.preferred_currency,
        "alert_warn_pct": user.alert_warn_pct,
        "alert_critical_pct": user.alert_critical_pct,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.get("/health")
def health():
    return {"status": "ok", "app": "FinMate", "llm_configured": settings.llm_configured}


@router.post("/auth/register", status_code=201)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    seed_categories(db, user.id)
    _set_cookie(response, create_access_token(user.id))
    return _public_user(user)


@router.post("/auth/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(request, "login", limit=10)
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    _set_cookie(response, create_access_token(user.id))
    return _public_user(user)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return _public_user(user)


@router.patch("/auth/me")
def update_me(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.name:
        user.name = payload.name.strip()
    if payload.preferred_currency:
        if payload.preferred_currency not in CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")
        user.preferred_currency = payload.preferred_currency
    if payload.alert_warn_pct is not None:
        user.alert_warn_pct = payload.alert_warn_pct
    if payload.alert_critical_pct is not None:
        user.alert_critical_pct = payload.alert_critical_pct
    if user.alert_critical_pct <= user.alert_warn_pct:
        raise HTTPException(status_code=400, detail="The higher alert must be above the first alert")
    db.commit()
    db.refresh(user)
    return _public_user(user)


@router.delete("/auth/me")
def delete_me(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import (
        Budget,
        CategorizationFeedback,
        Category,
        CategoryRule,
        Conversation,
        Goal,
        GoalContribution,
        ImportRecord,
        InsightDismissal,
        Message,
        RecurringItem,
        Transaction,
    )

    conversation_ids = [row.id for row in db.query(Conversation.id).filter(Conversation.user_id == user.id)]
    if conversation_ids:
        db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
    for model in (
        Conversation,
        InsightDismissal,
        RecurringItem,
        GoalContribution,
        Goal,
        Budget,
        CategoryRule,
        CategorizationFeedback,
        Transaction,
        ImportRecord,
        Category,
    ):
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    response.delete_cookie(settings.cookie_name, path="/")
    return {"deleted": True}


@router.get("/categories")
def categories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Category).filter(Category.user_id == user.id).order_by(Category.transaction_type, Category.name).all()
    return [
        {"id": row.id, "name": row.name, "transaction_type": row.transaction_type, "is_system": row.is_system}
        for row in rows
    ]


@router.post("/categories", status_code=201)
def create_category(payload: CategoryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.transaction_type not in {"income", "expense"}:
        raise HTTPException(status_code=400, detail="Type must be income or expense")
    exists = (
        db.query(Category)
        .filter(
            Category.user_id == user.id,
            Category.name.ilike(payload.name.strip()),
            Category.transaction_type == payload.transaction_type,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="That category already exists")
    row = Category(user_id=user.id, name=payload.name.strip(), transaction_type=payload.transaction_type, is_system=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "transaction_type": row.transaction_type, "is_system": False}


@router.delete("/categories/{category_id}")
def remove_category(category_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = get_user_category(db, user.id, category_id)
    if row.is_system:
        raise HTTPException(status_code=400, detail="Default categories stay in place so history remains readable")
    from app.models import Transaction

    used = db.query(Transaction).filter(Transaction.category_id == row.id).first()
    if used:
        raise HTTPException(status_code=400, detail="Move transactions out of this category before deleting it")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.get("/category-rules")
def rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(CategoryRule).options(joinedload(CategoryRule.category)).filter(CategoryRule.user_id == user.id).all()
    return [
        {
            "id": row.id,
            "pattern": row.pattern,
            "category_id": row.category_id,
            "category_name": row.category.name if row.category else None,
        }
        for row in rows
    ]


@router.post("/category-rules", status_code=201)
def create_rule(payload: RuleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_user_category(db, user.id, payload.category_id)
    row = CategoryRule(user_id=user.id, pattern=payload.pattern.strip().lower(), category_id=payload.category_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "pattern": row.pattern, "category_id": row.category_id}


@router.delete("/category-rules/{rule_id}")
def remove_rule(rule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(CategoryRule).filter(CategoryRule.id == rule_id, CategoryRule.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.get("/transactions")
def transactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start: date | None = None,
    end: date | None = None,
    category_id: int | None = None,
    type: str | None = Query(default=None),
    payment_method: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    search: str | None = None,
    sort: str = "date_desc",
    limit: int = 50,
    offset: int = 0,
):
    return list_transactions(
        db,
        user.id,
        start=start,
        end=end,
        category_id=category_id,
        tx_type=type,
        payment_method=payment_method,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post("/transactions", status_code=201)
def add_transaction(payload: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.type not in {"income", "expense"}:
        raise HTTPException(status_code=400, detail="Type must be income or expense")
    row = create_transaction(db, user.id, payload.model_dump())
    body = serialize_transaction(row)
    body["prediction"] = getattr(row, "prediction", None)
    return body


@router.patch("/transactions/{transaction_id}")
def patch_transaction(
    transaction_id: int,
    payload: TransactionPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    row = update_transaction(db, user.id, transaction_id, data)
    return serialize_transaction(row)


@router.delete("/transactions/{transaction_id}")
def remove_transaction(transaction_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_transaction(db, user.id, transaction_id)
    return {"deleted": True}


@router.get("/dashboard")
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    preset: str = "this_month",
    start: date | None = None,
    end: date | None = None,
):
    try:
        range_start, range_end = resolve_range(preset, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = query_transactions(db, user.id, range_start, range_end)
    summary = summarise(rows)
    year, month = range_end.year, range_end.month
    budgets = budget_status(db, user, year, month)
    return {
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
        "currency": user.preferred_currency,
        "summary": summary,
        "budget_utilisation": budgets["utilisation"],
        "budget_alerts": budgets["alerts"],
        "income_expense": monthly_series(rows),
        "categories": category_totals(rows, "expense"),
        "weekly": weekly_spending(rows),
        "top_categories": category_totals(rows, "expense")[:5],
        "recent": list_transactions(db, user.id, start=range_start, end=range_end, limit=8)["items"],
    }


@router.post("/imports/analyse")
async def import_analyse(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    return analyse_csv(file.filename or "statement.csv", content, user.id)


@router.post("/imports/preview")
def import_preview(payload: MappingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_preview(db, user.id, payload.preview_id, payload.mapping)


@router.post("/imports/commit")
def import_commit(payload: CommitIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    overrides = {}
    for row in payload.rows:
        if "index" not in row:
            continue
        overrides[int(row["index"])] = row
    return commit_preview(db, user.id, payload.preview_id, overrides)


@router.get("/imports")
def imports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_imports(db, user.id)


@router.get("/budgets")
def budgets(
    month: int | None = None,
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    return budget_status(db, user, year or today.year, month or today.month)


@router.post("/budgets", status_code=201)
def add_budget(payload: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = create_budget(db, user.id, payload.category_id, payload.monthly_limit, payload.month, payload.year)
    return {"id": row.id}


@router.patch("/budgets/{budget_id}")
def patch_budget(budget_id: int, payload: BudgetPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = update_budget(db, user.id, budget_id, payload.monthly_limit)
    return {"id": row.id, "monthly_limit": str(row.monthly_limit)}


@router.delete("/budgets/{budget_id}")
def remove_budget(budget_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_budget(db, user.id, budget_id)
    return {"deleted": True}


@router.post("/budgets/suggest")
def budget_suggest(
    month: int | None = None,
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    return suggest_budgets(db, user, year or today.year, month or today.month)


@router.get("/goals")
def goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_goals(db, user.id)


@router.post("/goals", status_code=201)
def add_goal(payload: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_goal(db, user.id, payload.name, payload.target_amount, payload.target_date)


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: int, payload: GoalPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return update_goal(db, user.id, goal_id, payload.model_dump(exclude_unset=True))


@router.delete("/goals/{goal_id}")
def remove_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_goal(db, user.id, goal_id)
    return {"deleted": True}


@router.post("/goals/{goal_id}/contributions", status_code=201)
def contribute(goal_id: int, payload: ContributionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return add_contribution(db, user.id, goal_id, payload.amount, payload.contributed_on, payload.note)


@router.delete("/goals/{goal_id}/contributions/{contribution_id}")
def remove_contribution(
    goal_id: int,
    contribution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return delete_contribution(db, user.id, goal_id, contribution_id)


@router.get("/analytics")
def analytics(
    preset: str = "last_3_months",
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        range_start, range_end = resolve_range(preset, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows = query_transactions(db, user.id, range_start, range_end)
    summary = summarise(rows)
    categories = category_totals(rows, "expense")
    return {
        "start": range_start.isoformat(),
        "end": range_end.isoformat(),
        "currency": user.preferred_currency,
        "income": summary["income"],
        "expenses": summary["expenses"],
        "net_cash_flow": summary["balance"],
        "savings_rate": summary["savings_rate"],
        "average_daily_spend": average_daily_spend(rows, range_start, range_end),
        "largest_expense": largest_expense(rows),
        "highest_category": categories[0] if categories else None,
        "categories": categories,
        "monthly": monthly_series(rows),
        "patterns": spending_patterns(db, user.id, range_end)["items"],
    }


@router.get("/analytics/compare")
def analytics_compare(
    month: int | None = None,
    year: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start, end = month_bounds(year, month)
    if (year, month) == (today.year, today.month):
        end = min(end, today)
    prev_year, prev_month = previous_month(year, month)
    prev_start, prev_end = month_bounds(prev_year, prev_month)
    comparison = compare_periods(
        query_transactions(db, user.id, start, end),
        query_transactions(db, user.id, prev_start, prev_end),
    )
    return {
        "label": start.strftime("%B %Y"),
        "previous_label": prev_start.strftime("%B %Y"),
        "currency": user.preferred_currency,
        **comparison,
    }


@router.get("/analytics/anomalies")
def anomalies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return detect_anomalies(db, user.id)


@router.get("/analytics/forecast")
def forecast(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_forecast(db, user.id)


@router.get("/insights")
def insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return generate_insights(db, user)


@router.post("/insights/dismiss")
def dismiss(payload: DismissIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dismiss_insight(db, user.id, payload.key)
    return {"dismissed": True}


@router.get("/recurring")
def recurring(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return detect_recurring(db, user.id)


@router.post("/recurring/{item_id}/confirm")
def confirm_recurring(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return set_status(db, user.id, item_id, "confirmed")


@router.post("/recurring/{item_id}/reject")
def reject_recurring(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return set_status(db, user.id, item_id, "rejected")


def _report_or_404(builder):
    return builder


@router.get("/reports/monthly")
def report_month(
    month: int,
    year: int,
    ai: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = monthly_report(db, user, year, month)
    if ai:
        try:
            report["ai_commentary"] = maybe_ai_commentary(report)
        except Exception:
            report["ai_commentary"] = None
            report["ai_error"] = "The language model request failed. The calculated report is unchanged."
    return report


@router.get("/reports/yearly")
def report_year(
    year: int,
    ai: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = yearly_report(db, user, year)
    if ai:
        try:
            report["ai_commentary"] = maybe_ai_commentary(report)
        except Exception:
            report["ai_commentary"] = None
            report["ai_error"] = "The language model request failed. The calculated report is unchanged."
    return report


@router.get("/reports/monthly/export")
def export_month(
    month: int,
    year: int,
    format: str = "csv",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = monthly_report(db, user, year, month)
    return _export(report, format, f"finmate-{year}-{month:02d}")


@router.get("/reports/yearly/export")
def export_year(
    year: int,
    format: str = "csv",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = yearly_report(db, user, year)
    return _export(report, format, f"finmate-{year}")


def _export(report: dict, format: str, stem: str):
    if format == "pdf":
        return Response(
            content=report_pdf(report),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
        )
    if format == "csv":
        return Response(
            content=report_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{stem}.csv"'},
        )
    raise HTTPException(status_code=400, detail="format must be pdf or csv")


@router.get("/assistant/status")
def assistant_status():
    return {
        "configured": settings.llm_configured,
        "model": settings.llm_model if settings.llm_configured else None,
        "base_url": settings.llm_base_url if settings.llm_configured else None,
    }


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.id.desc()).all()
    return [{"id": row.id, "title": row.title, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]


@router.post("/conversations", status_code=201)
def new_conversation(payload: ConversationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = Conversation(user_id=user.id, title=(payload.title or "New conversation")[:160])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title}


def _owned_conversation(db: Session, user_id: int, conversation_id: int) -> Conversation:
    row = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned_conversation(db, user.id, conversation_id)
    return [
        {"id": message.id, "role": message.role, "content": message.content, "created_at": message.created_at.isoformat()}
        for message in row.messages
        if message.role in {"user", "assistant"}
    ]


@router.delete("/conversations/{conversation_id}/messages")
def clear_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned_conversation(db, user.id, conversation_id)
    db.query(Message).filter(Message.conversation_id == row.id).delete()
    db.commit()
    return {"cleared": True}


@router.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned_conversation(db, user.id, conversation_id)
    db.delete(row)
    db.commit()
    return {"deleted": True}


def _sse(conversation: Conversation, db: Session, user: User):
    def generate():
        try:
            for event in iter_reply(db, user, conversation):
                yield f"event: {event['event']}\ndata: {json.dumps(event)}\n\n"
        except Exception as exc:
            payload = {"event": "error", "message": f"The assistant stopped ({exc.__class__.__name__})."}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    payload: ChatIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "assistant", limit=20)
    conversation = _owned_conversation(db, user.id, conversation_id)
    text = payload.content.strip()
    db.add(Message(conversation_id=conversation.id, role="user", content=text))
    if conversation.title == "New conversation":
        conversation.title = text[:48]
    db.commit()
    db.expire_all()
    conversation = _owned_conversation(db, user.id, conversation_id)
    return _sse(conversation, db, user)


@router.post("/conversations/{conversation_id}/regenerate")
def regenerate(
    conversation_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, "assistant", limit=20)
    conversation = _owned_conversation(db, user.id, conversation_id)
    if not conversation.messages:
        raise HTTPException(status_code=400, detail="There is no message to regenerate")
    if conversation.messages[-1].role == "assistant":
        db.delete(conversation.messages[-1])
        db.commit()
        db.expire_all()
        conversation = _owned_conversation(db, user.id, conversation_id)
    return _sse(conversation, db, user)


@router.post("/demo/load")
def demo_load(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return load_demo(db, user.id)


@router.delete("/demo")
def demo_clear(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return clear_demo(db, user.id)


@router.get("/meta")
def meta():
    return {"currencies": CURRENCIES, "payment_methods": PAYMENT_METHODS}
