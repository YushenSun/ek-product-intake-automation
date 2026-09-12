import pytest
from fastapi.testclient import TestClient

from backend.app.extraction.providers import MockExtractionProvider
from backend.app.main import app, get_batch_service, get_service, get_session
from backend.app.persistence.database import make_session_factory
from backend.app.services.batch import BatchService
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
def batch_service(factory):
    session = factory()
    yield BatchService(session, MockExtractionProvider())
    session.close()


@pytest.fixture
def client(factory):
    def service_override():
        session = factory()
        try:
            yield IntakeService(session, MockExtractionProvider())
        finally:
            session.close()

    def batch_service_override():
        session = factory()
        try:
            yield BatchService(session, MockExtractionProvider())
        finally:
            session.close()

    def session_override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_service] = service_override
    app.dependency_overrides[get_batch_service] = batch_service_override
    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
