"""Monthly and yearly reports. Facts are calculated here. AI text is optional and separate."""

import csv
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings
from app.money import D, money_str
from app.services.budgets import budget_status
from app.services.finance import category_totals, compare_periods, largest_expense, query_transactions, summarise
from app.services.patterns import spending_patterns
from app.services.periods import month_bounds, previous_month


def _computed_summary(summary: dict, top_category: dict | None, comparison: dict, currency: str) -> str:
    top = ""
    if top_category:
        top = f" The largest expense category was {top_category['category']} at {currency} {top_category['amount']}."
    change = comparison.get("expense_change_pct")
    change_text = "A previous period was not available for comparison."
    if change is not None:
        direction = "higher" if D(comparison["expense_delta"]) > 0 else "lower"
        change_text = f"Expenses were {abs(change)}% {direction} than the previous period."
    rate = summary["savings_rate"]
    rate_text = "Savings rate could not be calculated because income was zero."
    if rate is not None:
        rate_text = f"Savings rate was {rate}% (income minus expenses, when positive, divided by income)."
    return (
        f"Income was {currency} {summary['income']} and expenses were {currency} {summary['expenses']}. "
        f"The remaining balance was {currency} {summary['balance']}. {rate_text} {change_text}{top}"
    )


def build_report(db, user, start: date, end: date, label: str, budget_months: list[tuple[int, int]]) -> dict:
    rows = query_transactions(db, user.id, start, end)
    summary = summarise(rows)
    categories = category_totals(rows, "expense")
    # Previous window of the same length, ending the day before this window.
    length = (end - start).days + 1
    prev_end = start.fromordinal(start.toordinal() - 1)
    prev_start = prev_end.fromordinal(prev_end.toordinal() - length + 1)
    previous_rows = query_transactions(db, user.id, prev_start, prev_end)
    comparison = compare_periods(rows, previous_rows)
    budgets = [budget_status(db, user, year, month) for year, month in budget_months]
    patterns = spending_patterns(db, user.id, end)
    currency = user.preferred_currency
    top = categories[0] if categories else None
    return {
        "label": label,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "currency": currency,
        "summary": summary,
        "largest_expense": largest_expense(rows),
        "categories": categories,
        "comparison": {
            "previous_start": prev_start.isoformat(),
            "previous_end": prev_end.isoformat(),
            "expense_delta": comparison["expense_delta"],
            "expense_change_pct": comparison["expense_change_pct"],
            "income_delta": comparison["income_delta"],
            "categories": comparison["categories"][:8],
        },
        "budgets": [
            {
                "month": item["month"],
                "year": item["year"],
                "utilisation": item["utilisation"],
                "alerts": item["alerts"],
                "items": item["items"],
            }
            for item in budgets
        ],
        "patterns": patterns["items"],
        "computed_summary": _computed_summary(summary, top, comparison, currency),
        "ai_commentary": None,
    }


def monthly_report(db, user, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    label = start.strftime("%B %Y")
    return build_report(db, user, start, end, label, [(year, month)])


def yearly_report(db, user, year: int) -> dict:
    start, end = date(year, 1, 1), date(year, 12, 31)
    months = [(year, month) for month in range(1, 13)]
    return build_report(db, user, start, end, str(year), months)


def maybe_ai_commentary(report: dict) -> str | None:
    """Ask the LLM to comment on an already calculated report. Returns None if it cannot."""
    settings = get_settings()
    if not settings.llm_configured:
        return None
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    brief = {
        "label": report["label"],
        "summary": report["summary"],
        "top_categories": report["categories"][:5],
        "expense_change_pct": report["comparison"]["expense_change_pct"],
        "computed_summary": report["computed_summary"],
    }
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Write one short paragraph of financial commentary. Use only the JSON numbers. "
                    "Do not invent figures. Call forecasts estimates if you mention them. "
                    "Do not give this paragraph the tone of a guaranteed plan."
                ),
            },
            {"role": "user", "content": str(brief)},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    return text or None


def report_csv(report: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "name", "amount", "extra"])
    summary = report["summary"]
    for key in ("income", "expenses", "balance", "savings"):
        writer.writerow(["summary", key, summary[key], report["currency"]])
    writer.writerow(["summary", "savings_rate", summary["savings_rate"], "percent"])
    for item in report["categories"]:
        writer.writerow(["category", item["category"], item["amount"], item["count"]])
    writer.writerow(["computed_summary", report["computed_summary"], "", ""])
    if report.get("ai_commentary"):
        writer.writerow(["ai_commentary", report["ai_commentary"], "", ""])
    return buffer.getvalue()


def report_pdf(report: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("FinTitle", parent=styles["Title"], textColor=colors.HexColor("#0f6e6b"), fontSize=20)
    body = ParagraphStyle("FinBody", parent=styles["BodyText"], leading=15, fontSize=10)
    muted = ParagraphStyle("FinMuted", parent=body, textColor=colors.HexColor("#6f675e"))
    story = [
        Paragraph("FinMate", title_style),
        Paragraph(f"Financial report · {report['label']}", styles["Heading2"]),
        Paragraph("Figures in this report are calculated from your transactions. They are not estimates.", muted),
        Spacer(1, 8),
        Paragraph(report["computed_summary"], body),
        Spacer(1, 12),
        Paragraph("Category expenses", styles["Heading3"]),
    ]
    data = [["Category", "Amount", "Share", "Transactions"]]
    for item in report["categories"]:
        share = f"{item['share']}%" if item["share"] is not None else "—"
        data.append([item["category"], f"{report['currency']} {item['amount']}", share, str(item["count"])])
    if len(data) == 1:
        data.append(["No expenses in this period", "—", "—", "0"])
    table = Table(data, colWidths=[70 * mm, 40 * mm, 30 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6e6b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e4dcd0")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fffcf7")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))
    change = report["comparison"]["expense_change_pct"]
    change_text = "No percentage change (the previous period had no expenses)." if change is None else f"{change}% vs the previous window"
    story.append(Paragraph(f"Expense change: {change_text}. Delta {report['currency']} {report['comparison']['expense_delta']}.", body))
    if report["budgets"]:
        alerts = [alert for block in report["budgets"] for alert in block["alerts"]]
        if alerts:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Budget notes", styles["Heading3"]))
            for alert in alerts[:8]:
                story.append(Paragraph(f"• {alert}", body))
    if report.get("ai_commentary"):
        story.append(Spacer(1, 12))
        story.append(Paragraph("AI commentary", styles["Heading3"]))
        story.append(Paragraph("This paragraph is written by the language model from the figures above. It is not a new calculation.", muted))
        story.append(Paragraph(report["ai_commentary"], body))
    doc.build(story)
    return buffer.getvalue()


def previous_month_of(year: int, month: int) -> tuple[int, int]:
    return previous_month(year, month)
