import pytest
from fastapi.testclient import TestClient

from backend.app.extraction.providers import MockExtractionProvider
from backend.app.main import app, get_service, get_session
from backend.app.persistence.database import make_session_factory
from backend.app.services.intake import IntakeService


@pytest.fixture
def factory(tmp_path):
    return make_session_factory(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def service(factory):
    session = factory()
    yield IntakeService(session, MockExtractionProvider())
    session.close()


@pytest.fixture
def client(factory):
    def override():
        session = factory()
        try:
            yield IntakeService(session, MockExtractionProvider())
        finally:
            session.close()
    app.dependency_overrides[get_service] = override
    def session_override():
        session = factory()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
