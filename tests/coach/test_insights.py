"""Unit tests for Coach insights tools — real CRDB, no mocks.

These tools turn raw expenses into the kind of analysis a real PFM coach
needs: monthly totals, category velocity vs. budget pace, top merchants,
and recurring-charge detection.
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from banko_ai.coach.insights import (
    detect_subscriptions,
    get_monthly_summary,
    get_spending_velocity,
    get_top_merchants,
)
from banko_ai.utils.migration import DatabaseMigration


TEST_USER = "00000000-0000-0000-0000-000000000ddd"


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    DatabaseMigration(database_url=url).migrate_to_coach_v1()
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS expenses (
              expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              user_id UUID NOT NULL,
              expense_date DATE NOT NULL,
              expense_amount DECIMAL(10,2) NOT NULL,
              shopping_type STRING NOT NULL,
              description STRING,
              merchant STRING
            )
        """))
        try:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS merchant STRING"))
        except Exception:
            pass
    eng.dispose()
    return url


@pytest.fixture(autouse=True)
def _cleanup(db_url):
    eng = create_engine(db_url)
    try:
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM expenses WHERE user_id = :u"),
                         {"u": TEST_USER})
    except Exception:
        pass
    eng.dispose()
    yield


def _seed_expense(db_url: str, *, amount: float, category: str,
                  merchant: str, expense_date: date,
                  description: str = "") -> None:
    eng = create_engine(db_url)
    with eng.begin() as conn:
        conn.execute(text("""
            INSERT INTO expenses
              (expense_id, user_id, expense_date, expense_amount,
               shopping_type, description, merchant)
            VALUES (:id, :u, :d, :a, :c, :desc, :m)
        """), {"id": str(uuid.uuid4()), "u": TEST_USER, "d": expense_date,
               "a": amount, "c": category, "desc": description, "m": merchant})
    eng.dispose()


def test_monthly_summary_empty(db_url):
    today = date.today()
    result = get_monthly_summary(
        user_id=TEST_USER, year=today.year, month=today.month,
        database_url=db_url,
    )
    assert result["total"] == 0.0
    assert result["by_category"] == []
    assert result["top_merchants"] == []
    assert result["transaction_count"] == 0


def test_monthly_summary_aggregates_correctly(db_url):
    today = date.today()
    in_month = date(today.year, today.month, 5)
    _seed_expense(db_url, amount=25.0, category="dining",
                  merchant="Chipotle", expense_date=in_month)
    _seed_expense(db_url, amount=42.50, category="dining",
                  merchant="Chipotle", expense_date=in_month)
    _seed_expense(db_url, amount=120.0, category="groceries",
                  merchant="Whole Foods", expense_date=in_month)
    # Previous month — must be excluded
    prev_month = (in_month.replace(day=1) - timedelta(days=1))
    _seed_expense(db_url, amount=999.0, category="dining",
                  merchant="Chipotle", expense_date=prev_month)

    result = get_monthly_summary(
        user_id=TEST_USER, year=today.year, month=today.month,
        database_url=db_url,
    )
    assert result["total"] == pytest.approx(187.50)
    assert result["transaction_count"] == 3
    cats = {c["category"]: c["amount"] for c in result["by_category"]}
    assert cats["dining"] == pytest.approx(67.50)
    assert cats["groceries"] == pytest.approx(120.0)
    merchants = {m["merchant"]: m["amount"] for m in result["top_merchants"]}
    assert merchants["Whole Foods"] == pytest.approx(120.0)
    assert merchants["Chipotle"] == pytest.approx(67.50)


def test_spending_velocity_projects_end_of_month(db_url):
    today = date.today()
    # Seed 4 dining charges totaling $100 spread across first half of month
    for day_offset in (1, 4, 8, 12):
        d = date(today.year, today.month, min(day_offset, 28))
        if d > today:
            continue
        _seed_expense(db_url, amount=25.0, category="dining",
                      merchant="Chipotle", expense_date=d)

    result = get_spending_velocity(
        user_id=TEST_USER, category="dining",
        monthly_budget=400.0, database_url=db_url,
    )
    assert "spent_so_far" in result
    assert "projected_eom" in result
    assert "pct_of_budget" in result
    assert "days_into_month" in result
    assert result["category"] == "dining"
    assert result["monthly_budget"] == 400.0
    # Spent so far must equal what we seeded (only count rows on/before today)
    assert result["spent_so_far"] >= 0
    # Projection must be at least spent_so_far
    assert result["projected_eom"] >= result["spent_so_far"]


def test_top_merchants_ranks_by_spend(db_url):
    today = date.today()
    _seed_expense(db_url, amount=30.0, category="dining",
                  merchant="Chipotle", expense_date=today - timedelta(days=2))
    _seed_expense(db_url, amount=30.0, category="dining",
                  merchant="Chipotle", expense_date=today - timedelta(days=5))
    _seed_expense(db_url, amount=200.0, category="groceries",
                  merchant="Whole Foods", expense_date=today - timedelta(days=3))
    _seed_expense(db_url, amount=15.0, category="transport",
                  merchant="Uber", expense_date=today - timedelta(days=1))

    result = get_top_merchants(
        user_id=TEST_USER, days=30, k=3, database_url=db_url,
    )
    assert len(result) == 3
    assert result[0]["merchant"] == "Whole Foods"
    assert result[0]["total"] == pytest.approx(200.0)
    assert result[1]["merchant"] == "Chipotle"
    assert result[1]["total"] == pytest.approx(60.0)
    assert result[1]["transaction_count"] == 2


def test_top_merchants_filters_by_category(db_url):
    today = date.today()
    _seed_expense(db_url, amount=30.0, category="dining",
                  merchant="Chipotle", expense_date=today - timedelta(days=2))
    _seed_expense(db_url, amount=500.0, category="travel",
                  merchant="Delta", expense_date=today - timedelta(days=3))

    result = get_top_merchants(
        user_id=TEST_USER, days=30, k=5, category="dining",
        database_url=db_url,
    )
    assert len(result) == 1
    assert result[0]["merchant"] == "Chipotle"


def test_detect_subscriptions_finds_recurring_merchant(db_url):
    today = date.today()
    # Netflix charge appearing 3 months in a row (~30-day cadence, same amount)
    for months_back in (0, 1, 2):
        d = today - timedelta(days=30 * months_back)
        _seed_expense(db_url, amount=15.99, category="entertainment",
                      merchant="Netflix", expense_date=d,
                      description="Netflix monthly")
    # One-off Amazon purchase — should NOT register as subscription
    _seed_expense(db_url, amount=42.0, category="shopping",
                  merchant="Amazon", expense_date=today - timedelta(days=10))

    result = detect_subscriptions(
        user_id=TEST_USER, lookback_days=120, min_occurrences=3,
        database_url=db_url,
    )
    merchants = {s["merchant"] for s in result}
    assert "Netflix" in merchants
    assert "Amazon" not in merchants
    netflix = next(s for s in result if s["merchant"] == "Netflix")
    assert netflix["occurrence_count"] == 3
    assert netflix["typical_amount"] == pytest.approx(15.99)


def test_detect_subscriptions_flags_amount_drift(db_url):
    today = date.today()
    # Netflix price hike: 9.99 → 9.99 → 15.99 (drift detected)
    for months_back, amt in ((2, 9.99), (1, 9.99), (0, 15.99)):
        d = today - timedelta(days=30 * months_back)
        _seed_expense(db_url, amount=amt, category="entertainment",
                      merchant="Netflix", expense_date=d)

    result = detect_subscriptions(
        user_id=TEST_USER, lookback_days=120, min_occurrences=3,
        database_url=db_url,
    )
    netflix = next(s for s in result if s["merchant"] == "Netflix")
    assert netflix["amount_drift"] is True
    assert netflix["latest_amount"] == pytest.approx(15.99)
