import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import get_engine
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_database() -> None:
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
