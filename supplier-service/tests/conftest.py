import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import main


@pytest.fixture
def client(monkeypatch):
    """A client backed by a fresh, in-memory database for one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Production code calls get_engine() directly, so replace it for this test.
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    # Do not load the real CSV: create only the empty schema needed by the test.
    monkeypatch.setattr(
        main,
        "seed_database_from_csv",
        lambda _engine, _csv_path: main.Base.metadata.create_all(engine),
    )

    with TestClient(main.app) as test_client:
        yield test_client

    main.app.dependency_overrides.clear()
    main.Base.metadata.drop_all(engine)
