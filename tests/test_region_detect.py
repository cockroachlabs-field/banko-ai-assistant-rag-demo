"""Tests for multi-region detection and REGIONAL BY ROW migration."""

import os

import pytest
from sqlalchemy import create_engine, text

from banko_ai.utils.migration import (
    detect_regions,
    migrate_regional_tables,
    regional_tables_ready,
    resolve_primary_region,
)

DB = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="DATABASE_URL not set")


def test_detect_regions_unreachable_url():
    """When the database is unreachable, detect_regions returns empty list."""
    assert detect_regions("postgresql://root@nonexistent:26257/defaultdb") == []


def test_detect_regions_returns_cluster_regions():
    """On a multi-region cluster, detect_regions returns all regions."""
    regions = detect_regions(DB)
    if len(regions) >= 2:
        assert "us-east-1" in regions or "us-central-1" in regions or "us-west-2" in regions
    else:
        assert regions == []


def test_regional_migration_is_idempotent():
    """migrate_regional_tables can be called multiple times safely."""
    # Built with make_url so the scratch name applies no matter what the
    # real database is called; a naive string replace on "/defaultdb"
    # once left test_db == DB and dropped the real expenses table.
    from sqlalchemy.engine.url import make_url
    test_db = str(make_url(DB).set(database="banko_rbr_test"))
    assert make_url(test_db).database == "banko_rbr_test"

    engine = create_engine(DB)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE DATABASE IF NOT EXISTS banko_rbr_test"))
            conn.commit()

        engine_test = create_engine(test_db)
        with engine_test.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS expenses CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS spending_signals CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS coach_nudges CASCADE"))
            conn.execute(text("""
                CREATE TABLE expenses (
                    expense_id UUID PRIMARY KEY,
                    user_id UUID NOT NULL,
                    expense_date DATE,
                    expense_amount DECIMAL,
                    description STRING
                )
            """))
            conn.execute(text("""
                CREATE TABLE spending_signals (
                    signal_id UUID PRIMARY KEY,
                    user_id UUID NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE coach_nudges (
                    nudge_id UUID PRIMARY KEY,
                    user_id UUID NOT NULL
                )
            """))
            conn.commit()

        regions = detect_regions(test_db)
        if len(regions) < 2:
            assert migrate_regional_tables(test_db, primary_region=None) is False
        else:
            # Regression: on a fresh cluster, sample-data setup asks this
            # before the migration runs, and the cached False used to stick
            # for the process lifetime (no pinning, no pruning, no region
            # chip). A successful migration must invalidate it.
            assert regional_tables_ready(test_db) is False

            result1 = migrate_regional_tables(test_db, primary_region="us-east-1")
            assert result1 is True
            assert regional_tables_ready(test_db) is True

            result2 = migrate_regional_tables(test_db, primary_region="us-east-1")
            assert result2 is True

            with engine_test.connect() as conn:
                result = conn.execute(text("SHOW CREATE TABLE expenses"))
                row = result.fetchone()
                if row:
                    create_stmt = str(row[1])
                    assert "REGIONAL BY ROW" in create_stmt

    finally:
        with engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS banko_rbr_test CASCADE"))
            conn.commit()
        engine.dispose()


def test_resolve_primary_region_returns_existing_primary():
    """On a multi-region database with primary set, resolve_primary_region returns it."""
    regions = detect_regions(DB)
    if len(regions) >= 2:
        primary = resolve_primary_region(DB)
        assert primary in regions
    else:
        primary = resolve_primary_region(DB)
        assert primary is None


def test_resolve_primary_region_single_region_returns_none():
    """On single-region deployments, resolve_primary_region returns None."""
    unreachable = "postgresql://root@nonexistent:26257/defaultdb"
    assert resolve_primary_region(unreachable) is None
