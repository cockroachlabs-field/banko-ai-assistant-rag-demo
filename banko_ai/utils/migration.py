"""
Database migration utilities.

This module provides migration scripts to update the database schema
for user-specific vector indexing and other enhancements.
"""

import logging
import os
from functools import lru_cache
from typing import Optional

from .db_retry import get_database_url

log = logging.getLogger("banko.migration")


def is_regional_deployment(database_url: str) -> bool:
    """Check if database is multi-region (cached wrapper around detect_regions)."""
    return len(detect_regions(database_url)) >= 2


@lru_cache(maxsize=8)
def regional_tables_ready(database_url: str) -> bool:
    """True only when the cluster is multi-region AND the RBR migration
    actually applied (expenses carries crdb_region). Readers and writers
    gate on this, not on is_regional_deployment, so a failed or skipped
    migration degrades to single-region behavior instead of generating
    SQL against a column that does not exist."""
    if not is_regional_deployment(database_url):
        return False

    from sqlalchemy import text

    from .db_retry import create_resilient_engine

    try:
        engine = create_resilient_engine(database_url)
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'expenses' AND column_name = 'crdb_region'
                LIMIT 1
            """)).fetchone()
            return row is not None
    except Exception as e:
        log.debug("regional readiness check failed, treating as single-region: %s", e)
        return False
    finally:
        if 'engine' in locals():
            engine.dispose()


@lru_cache(maxsize=8)
def detect_regions(database_url: str) -> list[str]:
    """Detect cluster regions from SHOW REGIONS FROM CLUSTER.

    Returns empty list on single-region deployments, unreachable databases,
    or when fewer than two regions exist.

    Cached per URL to avoid repeated queries during a session.
    """
    from sqlalchemy import text

    from .db_retry import create_resilient_engine

    try:
        engine = create_resilient_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SHOW REGIONS FROM CLUSTER"))
            rows = result.fetchall()
            regions = [str(row[0]) for row in rows]
            if len(regions) < 2:
                return []
            return regions
    except Exception as e:
        log.debug("region detection failed (single-region or unreachable): %s", e)
        return []
    finally:
        if 'engine' in locals():
            engine.dispose()


def resolve_primary_region(database_url: str) -> str | None:
    """Resolve the primary region for migrate_regional_tables.

    Returns the database's current PRIMARY REGION if one is already set,
    else the gateway region, else the first detected region. Returns None
    if the deployment is single-region or unreachable.

    Never re-homes an existing primary: if the DB already has a primary
    region, that region is returned to make SET PRIMARY REGION idempotent.
    """
    from sqlalchemy import text

    from .db_retry import create_resilient_engine

    regions = detect_regions(database_url)
    if not regions:
        return None

    try:
        engine = create_resilient_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text('SELECT region FROM [SHOW REGIONS FROM DATABASE] WHERE "primary"'))
            row = result.fetchone()
            if row:
                return str(row[0])

            result = conn.execute(text("SELECT gateway_region()"))
            row = result.fetchone()
            if row and row[0]:
                gateway = str(row[0])
                if gateway in regions:
                    return gateway

            return regions[0]
    except Exception as e:
        log.debug("primary region resolution failed, falling back to first detected: %s", e)
        return regions[0]
    finally:
        if 'engine' in locals():
            engine.dispose()


def migrate_regional_tables(database_url: str, primary_region: str | None) -> bool:
    """Idempotently apply REGIONAL BY ROW locality to expenses, spending_signals,
    and coach_nudges tables.

    Returns False immediately when fewer than two regions detected (no-op).
    Returns True when multi-region DDL succeeds or is already applied.

    Args:
        database_url: Database connection string
        primary_region: Region to designate as PRIMARY REGION (required when
                        multi-region is detected)
    """
    import re

    from sqlalchemy import text

    from .db_retry import create_resilient_engine

    regions = detect_regions(database_url)
    if len(regions) < 2:
        log.info("single-region deployment detected, skipping REGIONAL BY ROW migration")
        return False

    if not primary_region:
        log.error("primary_region required for multi-region migration but was None")
        return False

    db_name = database_url.split("/")[-1].split("?")[0]
    identifier_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")

    if not identifier_pattern.match(db_name):
        log.error("invalid database name for DDL interpolation: %s", db_name)
        return False

    if not identifier_pattern.match(primary_region):
        log.error("invalid primary_region for DDL interpolation: %s", primary_region)
        return False

    for region in regions:
        if not identifier_pattern.match(region):
            log.error("invalid region name for DDL interpolation: %s", region)
            return False

    engine = create_resilient_engine(database_url)
    try:
        with engine.connect() as conn:
            log.info("applying multi-region config to database %s (primary: %s)", db_name, primary_region)

            try:
                conn.execute(text(f"ALTER DATABASE {db_name} SET PRIMARY REGION '{primary_region}'"))
                log.info("set PRIMARY REGION to %s", primary_region)
            except Exception as e:
                if "already set" in str(e).lower() or "already exists" in str(e).lower():
                    log.debug("PRIMARY REGION already set: %s", e)
                else:
                    raise

            for region in regions:
                if region == primary_region:
                    continue
                try:
                    conn.execute(text(f"ALTER DATABASE {db_name} ADD REGION '{region}'"))
                    log.info("added region %s", region)
                except Exception as e:
                    if "already added" in str(e).lower() or "already exists" in str(e).lower():
                        log.debug("region %s already added: %s", region, e)
                    else:
                        raise

            # Table names are hardcoded here (not user input), safe to interpolate
            for table in ["expenses", "spending_signals", "coach_nudges"]:
                try:
                    conn.execute(text(f"ALTER TABLE {table} SET LOCALITY REGIONAL BY ROW"))
                    log.info("set %s to REGIONAL BY ROW", table)
                except Exception as e:
                    if "already regional by row" in str(e).lower() or "locality already set" in str(e).lower():
                        log.debug("%s already REGIONAL BY ROW: %s", table, e)
                    else:
                        raise

            conn.commit()
            log.info("multi-region migration completed successfully")
            return True

    except Exception as e:
        log.exception("multi-region migration failed: %s", e)
        return False
    finally:
        engine.dispose()


class DatabaseMigration:
    """Database migration utilities."""
    
    def __init__(self, database_url: str | None = None):
        """Initialize migration manager."""
        self.database_url = get_database_url(database_url)
        self._engine = None
    
    @property
    def engine(self):
        """Get SQLAlchemy engine (lazy import)."""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(self.database_url)
        return self._engine
    
    def migrate_to_user_specific_indexing(self) -> bool:
        """Migrate database to support user-specific vector indexing."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                # Check if user_id column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'expenses' AND column_name = 'user_id'
                """))
                
                if not result.fetchone():
                    # Add user_id column if it doesn't exist
                    conn.execute(text("""
                        ALTER TABLE expenses 
                        ADD COLUMN user_id UUID DEFAULT gen_random_uuid()
                    """))
                    print("Added user_id column to expenses table")
                
                # Create user-specific vector index
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_expenses_user_embedding 
                    ON expenses (user_id, embedding) 
                    USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 100)
                """))
                print("Created user-specific vector index")
                
                # Create regional index if supported
                try:
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_expenses_user_embedding_regional 
                        ON expenses (user_id, embedding) 
                        LOCALITY REGIONAL BY ROW AS region
                    """))
                    print("Created regional user-specific vector index")
                except Exception as e:
                    print(f"Regional indexing not supported: {e}")
                
                # Create additional indexes for user queries
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_expenses_user_date 
                    ON expenses (user_id, expense_date DESC)
                """))
                print("Created user date index")
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Migration failed: {e}")
            return False
    
    def add_created_at_column(self) -> bool:
        """Add created_at timestamp column."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                # Check if created_at column exists
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'expenses' AND column_name = 'created_at'
                """))

                if not result.fetchone():
                    conn.execute(text("""
                        ALTER TABLE expenses
                        ADD COLUMN created_at TIMESTAMP DEFAULT now()
                    """))
                    print("Added created_at column to expenses table")
                    conn.commit()
                    return True
                else:
                    print("created_at column already exists")
                    return True

        except Exception as e:
            print(f"Failed to add created_at column: {e}")
            return False

    def migrate_users_table(self) -> bool:
        """Create users table for real user signup."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users (
                      user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      username        STRING NOT NULL UNIQUE,
                      spending_style  STRING NOT NULL,
                      home_region     STRING,
                      created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                      demo_user       BOOL NOT NULL DEFAULT true
                    )
                """))
                print("Created users table")
                conn.commit()

                ttl_days = int(os.getenv("DEMO_USER_TTL_DAYS", "0"))
                if ttl_days > 0:
                    try:
                        conn.execute(text(f"""
                            ALTER TABLE users
                            SET (ttl_expire_after = '{ttl_days} days')
                        """))
                        print(f"Applied demo user TTL: {ttl_days} days")
                        conn.commit()
                    except Exception as e:
                        print(f"Demo user TTL application failed (non-fatal): {e}")

                return True

        except Exception as e:
            print(f"Users table migration failed: {e}")
            return False

    def migrate_to_coach_v1(self) -> bool:
        """Create spending_signals and coach_nudges tables for the Coach v1
        feature. Both tables use row-level TTL matching the LangGraph
        checkpoint pattern."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS spending_signals (
                      signal_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id         UUID NOT NULL,
                      signal_type     STRING NOT NULL,
                      severity        STRING NOT NULL,
                      payload         JSONB NOT NULL,
                      produced_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                      consumed_at     TIMESTAMPTZ,
                      idempotency_key STRING NOT NULL UNIQUE,
                      INDEX (user_id, produced_at DESC)
                    ) WITH (ttl_expire_after = '30 days')
                """))
                print("Created spending_signals table")

                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS coach_nudges (
                      nudge_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      signal_id      UUID REFERENCES spending_signals(signal_id),
                      user_id        UUID NOT NULL,
                      message        STRING NOT NULL,
                      tool_trace     JSONB,
                      provider_used  STRING,
                      trace_id       STRING,
                      created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                      INDEX (user_id, created_at DESC)
                    ) WITH (ttl_expire_after = '90 days')
                """))
                print("Created coach_nudges table")

                # set_budget creates this lazily, but get_user_budget can run
                # first (the nudge planner reads budgets), so it has to exist
                # from boot like the other coach tables.
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_budgets (
                      user_id   UUID NOT NULL,
                      category  STRING NOT NULL,
                      amount    DECIMAL NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                      PRIMARY KEY (user_id, category)
                    )
                """))
                print("Created user_budgets table")

                conn.commit()
                return True

        except Exception as e:
            print(f"Coach v1 migration failed: {e}")
            return False

    def run_all_migrations(self) -> bool:
        """Run all pending migrations."""
        print("Running database migrations...")

        success = True
        success &= self.add_created_at_column()
        success &= self.migrate_to_user_specific_indexing()
        success &= self.migrate_to_coach_v1()

        if success:
            print("All migrations completed successfully")
        else:
            print("Some migrations failed")

        return success
