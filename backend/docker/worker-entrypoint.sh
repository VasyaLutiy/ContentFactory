#!/bin/sh
set -eu

python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

database_url = os.getenv("CONTENT_FACTORY_DATABASE_URL")
if database_url and not database_url.startswith("sqlite"):
    deadline = time.monotonic() + int(os.getenv("CONTENT_FACTORY_DB_WAIT_SECONDS", "60"))
    while True:
        try:
            engine = create_engine(database_url, future=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)

from app.db.init_db import init_db

init_db()
print("ContentFactory worker standby started; persistent queue runtime is not wired yet.", flush=True)
PY

exec python -c "import time; time.sleep(31536000)"
