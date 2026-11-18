"""Decimal helpers. Amounts stay at two decimal places."""

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")


def D(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def money_str(value) -> str:
    return format(D(value), "f")


def pct(part, whole) -> float | None:
    whole_d = D(whole)
    if whole_d == 0:
        return None
    return float((D(part) / whole_d * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
