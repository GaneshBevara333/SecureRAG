import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure test environment variables are set BEFORE any app module imports
os.environ["USE_MOCK_EMBEDDINGS"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from app.config import get_settings
get_settings.cache_clear()

from app.db.session import Base, get_db
from app.main import app
from app.llm import providers
from app.llm.providers import StubChatModel
from app.retrieval.embed import default_embedding_service
from app.retrieval.rerank import default_reranker_service

# Ensure mock services are loaded and active for tests
default_embedding_service.use_mock = True
default_reranker_service.use_mock = True

from sqlalchemy.pool import StaticPool

# Create in-memory SQLite engine for tests with StaticPool
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def mock_llm_providers_by_default(monkeypatch):
    """Ensure all tests default to StubChatModel (zero real Groq/Gemini network calls)."""
    stub = StubChatModel()
    monkeypatch.setattr(providers, "get_llm", lambda *args, **kwargs: stub)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database tables for each test and clean up afterwards."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
