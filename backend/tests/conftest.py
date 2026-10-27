import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import get_settings


@pytest.fixture
def db_session():
    # Needs the Docker Postgres with migrations applied (alembic upgrade head).
    # CI has no Postgres service, so this is skipped there.
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM tracks LIMIT 1"))
    except (OperationalError, ProgrammingError):
        # OperationalError: Postgres is down; ProgrammingError: migrations not applied.
        pytest.skip("Postgres with the tracks table is not available")
    with engine.connect() as conn:
        transaction = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()
