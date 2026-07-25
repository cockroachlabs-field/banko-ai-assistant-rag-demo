import os

# Normalize the scheme once for every test module: postgresql:// works for
# the app (it normalizes internally), so it should work for the suite too.
from banko_ai.utils.db_retry import normalize_db_url

if os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = normalize_db_url(os.environ["DATABASE_URL"])
