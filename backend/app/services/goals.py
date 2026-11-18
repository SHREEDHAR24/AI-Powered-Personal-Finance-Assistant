"""Savings goals. Current amount is the sum of contributions the user recorded."""

import math
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Goal, GoalContribution
from app.money import D, money_str, pct


def _months_left(today: date, target: date) -> int:
    if target <= today:
        return 0
    return max(1, math.ceil((target - today).days / 30))


def serialize_goal(goal: Goal, today: date | None = None) -> dict:
    today = today or date.today()
    saved = sum((D(item.amount) for item in goal.contributions), D(0))
    target = D(goal.target_amount)
    remaining = target - saved
    if remaining < 0:
        remaining = D(0)
    months = _months_left(today, goal.target_date)
    required = None
    if months > 0 and remaining > 0:
        required = money_str(remaining / months)
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": money_str(target),
        "current_amount": money_str(saved),
        "remaining_amount": money_str(remaining),
        "target_date": goal.target_date.isoformat(),
        "progress": pct(saved, target),
        "months_left": months,
        "required_monthly": required,
        "target_passed": goal.target_date < today and remaining > 0,
        "contributions": [
            {
                "id": item.id,
                "amount": money_str(item.amount),
                "contributed_on": item.contributed_on.isoformat(),
                "note": item.note,
            }
            for item in sorted(goal.contributions, key=lambda item: item.contributed_on, reverse=True)
        ],
    }


def list_goals(db: Session, user_id: int) -> list[dict]:
    rows = db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.target_date.asc()).all()
    return [serialize_goal(row) for row in rows]


def create_goal(db: Session, user_id: int, name: str, target_amount, target_date: date) -> dict:
    goal = Goal(user_id=user_id, name=name.strip(), target_amount=D(target_amount), target_date=target_date)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def update_goal(db: Session, user_id: int, goal_id: int, payload: dict) -> dict:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    if payload.get("name"):
        goal.name = payload["name"].strip()
    if payload.get("target_amount") is not None:
        goal.target_amount = D(payload["target_amount"])
    if payload.get("target_date") is not None:
        goal.target_date = payload["target_date"]
    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def delete_goal(db: Session, user_id: int, goal_id: int) -> None:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()


def add_contribution(db: Session, user_id: int, goal_id: int, amount, contributed_on: date, note: str | None) -> dict:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.add(
        GoalContribution(
            goal_id=goal.id,
            user_id=user_id,
            amount=D(amount),
            contributed_on=contributed_on,
            note=note,
        )
    )
    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)


def delete_contribution(db: Session, user_id: int, goal_id: int, contribution_id: int) -> dict:
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    row = (
        db.query(GoalContribution)
        .filter(
            GoalContribution.id == contribution_id,
            GoalContribution.goal_id == goal_id,
            GoalContribution.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Contribution not found")
    db.delete(row)
    db.commit()
    db.refresh(goal)
    return serialize_goal(goal)
