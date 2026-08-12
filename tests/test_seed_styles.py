import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from banko_ai.vector_search.generator import EnhancedExpenseGenerator

DB = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="DATABASE_URL not set")


@pytest.fixture
def user_id():
    uid = str(uuid.uuid4())
    yield uid
    # Cleanup retries: on a shared cluster the delete can lose a
    # RETRY_SERIALIZABLE race with a running app and fail the whole
    # gate from teardown.
    import time
    eng = create_engine(DB)
    for attempt in range(4):
        try:
            with eng.begin() as c:
                c.execute(text("DELETE FROM expenses WHERE user_id = :u"), {"u": uid})
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(0.5 * (attempt + 1))
    eng.dispose()


def test_diner_style_is_restaurant_heavy(user_id):
    gen = EnhancedExpenseGenerator(DB)
    n = gen.seed_user_history(user_id, "diner")
    assert n > 40
    eng = create_engine(DB)
    with eng.connect() as c:
        total, rest = c.execute(text("""
            SELECT count(*),
                   count(*) FILTER (WHERE shopping_type = 'Restaurant')
            FROM expenses WHERE user_id = :u"""), {"u": user_id}).fetchone()
    eng.dispose()
    assert rest / total > 0.3
    # embeddings present so vector search works immediately
    with create_engine(DB).connect() as c:
        missing = c.execute(text(
            "SELECT count(*) FROM expenses WHERE user_id = :u "
            "AND embedding IS NULL"), {"u": user_id}).scalar()
    assert missing == 0


def test_seeding_is_idempotent(user_id):
    gen = EnhancedExpenseGenerator(DB)
    first = gen.seed_user_history(user_id, "subscriber")
    second = gen.seed_user_history(user_id, "subscriber")
    assert second == 0 and first > 0
