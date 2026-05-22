"""
Database migration utilities.

This module provides migration scripts to update the database schema
for user-specific vector indexing and other enhancements.
"""

import os
from typing import Optional

from .db_retry import get_database_url


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
