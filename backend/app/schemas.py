"""Request bodies. Responses are plain dicts built by the services."""

from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_currency: str | None = None
    alert_warn_pct: int | None = Field(default=None, ge=1, le=99)
    alert_critical_pct: int | None = Field(default=None, ge=1, le=100)


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    transaction_type: str


class TransactionIn(BaseModel):
    date: Date
    description: str = Field(min_length=1, max_length=300)
    amount: Decimal = Field(gt=0, le=Decimal("100000000"))
    type: str
    category_id: int | None = None
    payment_method: str = "UPI"
    merchant: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)


class TransactionPatch(BaseModel):
    date: Date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=300)
    amount: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))
    type: str | None = None
    category_id: int | None = None
    payment_method: str | None = None
    merchant: str | None = None
    notes: str | None = None


class RuleIn(BaseModel):
    pattern: str = Field(min_length=2, max_length=120)
    category_id: int


class MappingIn(BaseModel):
    preview_id: str
    mapping: dict[str, str | None]


class CommitIn(BaseModel):
    preview_id: str
    rows: list[dict] = []


class BudgetIn(BaseModel):
    category_id: int
    monthly_limit: Decimal = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class BudgetPatch(BaseModel):
    monthly_limit: Decimal = Field(gt=0)


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: Decimal = Field(gt=0)
    target_date: Date


class GoalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_amount: Decimal | None = Field(default=None, gt=0)
    target_date: Date | None = None


class ContributionIn(BaseModel):
    amount: Decimal = Field(gt=0)
    contributed_on: Date
    note: str | None = Field(default=None, max_length=240)


class DismissIn(BaseModel):
    key: str = Field(min_length=1, max_length=160)


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=160)
