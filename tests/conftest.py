import pytest

from database.db import create_session_factory, init_db
from database.repository import TelemetryRepository


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "test.db"

    init_db(db_path)
    session_factory = create_session_factory(db_path)

    yield TelemetryRepository(session_factory)

    session_factory.kw["bind"].dispose()