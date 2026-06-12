import os
from pathlib import Path

from sqlmodel import create_engine

if os.getenv("TESTING"):
    _db_url = (
        f"postgresql://"
        f"{os.environ['POSTGRES_USER']}:"
        f"{os.environ['POSTGRES_PASSWORD']}"
        f"@db:5432/{os.environ['POSTGRES_DB']}"
    )
else:
    _db_url = (
        f"postgresql://"
        f"{os.environ['POSTGRES_USER']}:"
        f"{Path('/run/secrets/postgres_pwd').read_text().strip()}"
        f"@db:5432/{os.environ['POSTGRES_DB']}"
    )
engine = create_engine(_db_url, echo=True)
