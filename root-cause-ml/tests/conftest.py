import os

# main.py imports train.py, which raises at import time when DB_URL is unset.
# This has to run before any test module imports main, so it lives at the top
# of conftest rather than inside a fixture.
os.environ.setdefault("DB_URL", "postgresql://test:test@localhost:5432/test")
