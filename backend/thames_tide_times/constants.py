from sqlmodel import create_engine

_sqlite_file_name = "database.db"
_sqlite_url = f"sqlite:///{_sqlite_file_name}"
engine = create_engine(_sqlite_url, echo=True)
