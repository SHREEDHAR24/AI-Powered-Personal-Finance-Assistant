"""Turn dashboard presets into concrete dates."""

from datetime import date, timedelta


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def add_months(day: date, delta: int) -> date:
    month = day.month - 1 + delta
    year = day.year + month // 12
    month = month % 12 + 1
    # Clamp the day for short months.
    last = month_bounds(year, month)[1].day
    return date(year, month, min(day.day, last))


def resolve_range(
    preset: str | None,
    start: date | None,
    end: date | None,
    today: date | None = None,
) -> tuple[date, date]:
    today = today or date.today()
    preset = preset or "this_month"
    if preset == "this_week":
        return today - timedelta(days=today.weekday()), today
    if preset == "this_month":
        return today.replace(day=1), today
    if preset == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if preset == "last_3_months":
        start_month = add_months(today.replace(day=1), -2)
        return start_month, today
    if preset == "custom":
        if start is None or end is None:
            raise ValueError("Custom range needs a start and end date")
        if end < start:
            raise ValueError("End date is before the start date")
        return start, end
    raise ValueError("Unknown date range")


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def months_between(start: date, end: date) -> int:
    """Whole months from start to end, minimum 0. A partial month still counts as 1 when end is later."""
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        months += 0
    return max(months, 1) if end > start else 0
