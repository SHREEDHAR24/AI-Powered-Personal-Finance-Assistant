"""Layered categorisation.

Order: the user's own rules, then the built-in keyword list, then a text
model trained on that user's corrections. An optional LLM fallback exists
for a single description and only when the user turns it on. Predictions
are always checked against the user's real categories.
"""

from __future__ import annotations

import re
from functools import lru_cache

from sqlalchemy.orm import Session

from app.constants import KEYWORD_RULES
from app.core.config import get_settings
from app.models import CategorizationFeedback, Category, CategoryRule
from app.services.categories import category_by_name, other_category

_model_cache: dict[int, tuple[int, object, object]] = {}


def clean_text(value: str | None) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _keyword_match(text: str) -> tuple[str, str, float] | None:
    best: tuple[str, str, float] | None = None
    best_len = 0
    for name, tx_type, words in KEYWORD_RULES:
        for word in words:
            if word in text and len(word) > best_len:
                best = (name, tx_type, 0.92 if len(word) >= 8 else 0.86)
                best_len = len(word)
    return best


def _user_rule(db: Session, user_id: int, text: str) -> Category | None:
    rules = db.query(CategoryRule).filter(CategoryRule.user_id == user_id).all()
    # Longer patterns win so "amazon prime" beats "amazon".
    rules.sort(key=lambda rule: len(rule.pattern), reverse=True)
    for rule in rules:
        if rule.pattern.lower().strip() in text:
            category = db.get(Category, rule.category_id)
            if category and category.user_id == user_id:
                return category
    return None


def _train_user_model(db: Session, user_id: int):
    rows = (
        db.query(CategorizationFeedback)
        .filter(CategorizationFeedback.user_id == user_id)
        .all()
    )
    if len(rows) < 30:
        return None
    labels = []
    texts = []
    for row in rows:
        category = db.get(Category, row.corrected_category_id)
        if category is None or category.user_id != user_id:
            continue
        texts.append(clean_text(row.description))
        labels.append(category.name)
    if len(set(labels)) < 2 or len(texts) < 30:
        return None
    cached = _model_cache.get(user_id)
    if cached and cached[0] == len(rows):
        return cached[1], cached[2]
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=400)),
        ]
    )
    model.fit(texts, labels)
    _model_cache[user_id] = (len(rows), model, None)
    return model, None


def _ml_match(db: Session, user_id: int, text: str) -> tuple[str, float] | None:
    trained = _train_user_model(db, user_id)
    if trained is None:
        return None
    model, _ = trained
    probabilities = model.predict_proba([text])[0]
    index = int(probabilities.argmax())
    confidence = float(probabilities[index])
    if confidence < 0.55:
        return None
    return str(model.classes_[index]), confidence


def _llm_match(description: str, allowed: list[str]) -> str | None:
    settings = get_settings()
    if not settings.llm_configured or not settings.llm_categorize_fallback:
        return None
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    allowed_text = ", ".join(allowed)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify one bank narration. Reply with only the category name "
                    f"from this list: {allowed_text}. If none fit, reply Other."
                ),
            },
            {"role": "user", "content": description[:300]},
        ],
    )
    name = (response.choices[0].message.content or "").strip()
    allowed_lookup = {item.casefold(): item for item in allowed}
    return allowed_lookup.get(name.casefold())


def predict_category(
    db: Session,
    user_id: int,
    description: str,
    merchant: str | None = None,
    tx_type: str | None = None,
    allow_llm: bool = False,
) -> dict:
    """Return a category the user actually owns, plus how it was chosen."""
    text = clean_text(f"{description} {merchant or ''}")
    rule = _user_rule(db, user_id, text)
    if rule and (tx_type is None or rule.transaction_type == tx_type):
        return _result(rule, 0.99, "user_rule")

    keyword = _keyword_match(text)
    if keyword:
        name, guessed_type, confidence = keyword
        if tx_type is None or guessed_type == tx_type:
            found = category_by_name(db, user_id, name, guessed_type)
            if found:
                return _result(found, confidence, "keyword")

    ml = _ml_match(db, user_id, text)
    if ml:
        name, confidence = ml
        found = category_by_name(db, user_id, name, tx_type)
        if found:
            return _result(found, round(confidence, 2), "model")

    resolved_type = tx_type or "expense"
    if allow_llm:
        allowed = [
            row.name
            for row in db.query(Category).filter(
                Category.user_id == user_id,
                Category.transaction_type == resolved_type,
            )
        ]
        try:
            llm_name = _llm_match(description, allowed)
        except Exception:
            llm_name = None
        if llm_name:
            found = category_by_name(db, user_id, llm_name, resolved_type)
            if found:
                return _result(found, 0.6, "llm")

    fallback = other_category(db, user_id, resolved_type)
    return _result(fallback, 0.2, "fallback")


def _result(category: Category, confidence: float, source: str) -> dict:
    return {
        "category_id": category.id,
        "category_name": category.name,
        "transaction_type": category.transaction_type,
        "confidence": confidence,
        "source": source,
    }


def record_correction(
    db: Session,
    user_id: int,
    description: str,
    predicted_category_id: int | None,
    corrected_category_id: int,
) -> None:
    if predicted_category_id == corrected_category_id:
        return
    db.add(
        CategorizationFeedback(
            user_id=user_id,
            description=description[:300],
            predicted_category_id=predicted_category_id,
            corrected_category_id=corrected_category_id,
        )
    )
    _model_cache.pop(user_id, None)


@lru_cache
def keyword_catalog() -> tuple:
    return tuple(KEYWORD_RULES)
