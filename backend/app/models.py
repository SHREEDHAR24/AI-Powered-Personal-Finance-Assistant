"""Database tables. Every financial row belongs to one user."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_currency: Mapped[str] = mapped_column(String(8), default="INR")
    alert_warn_pct: Mapped[int] = mapped_column(Integer, default=75)
    alert_critical_pct: Mapped[int] = mapped_column(Integer, default=90)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    categories: Mapped[list["Category"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", "transaction_type", name="uq_category_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    transaction_type: Mapped[str] = mapped_column(String(16))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="categories")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_user_date", "user_id", "date"),
        Index("ix_tx_user_hash", "user_id", "duplicate_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    type: Mapped[str] = mapped_column(String(16))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    payment_method: Mapped[str] = mapped_column(String(32), default="Other")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id"), nullable=True)
    duplicate_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="transactions")
    category: Mapped[Category] = relationship()


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pattern: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category] = relationship()


class CategorizationFeedback(Base):
    __tablename__ = "categorization_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(300))
    predicted_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corrected_category_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportRecord(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    import_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    successful_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "month", "year", name="uq_budget_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    monthly_limit: Mapped[float] = mapped_column(Numeric(14, 2))
    month: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category] = relationship()


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    target_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contributions: Mapped[list["GoalContribution"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    contributed_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    goal: Mapped[Goal] = relationship(back_populates="contributions")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tool_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class InsightDismissal(Base):
    __tablename__ = "insight_dismissals"
    __table_args__ = (UniqueConstraint("user_id", "insight_key", name="uq_insight_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    insight_key: Mapped[str] = mapped_column(String(160))
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecurringItem(Base):
    __tablename__ = "recurring_items"
    __table_args__ = (UniqueConstraint("user_id", "fingerprint", name="uq_recurring_fp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="suggested")
    estimated_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    cadence: Mapped[str] = mapped_column(String(16))
    previous_dates: Mapped[str] = mapped_column(Text, default="[]")
    next_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
