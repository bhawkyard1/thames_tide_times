import os
from pathlib import Path

from sqlmodel import create_engine

_db_url = (
    f"postgresql://"
    f"{os.environ['POSTGRES_USER']}:"
    f"{Path('/run/secrets/postgres_pwd').read_text().strip()}"
    f"@db:5432/{os.environ['POSTGRES_DB']}"
)
engine = create_engine(_db_url, echo=True)
