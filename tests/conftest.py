import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def engine() -> Engine:
    original_database_url = settings.database_url
    settings.database_url = settings.test_database_url
    try:
        alembic_config = Config("alembic.ini")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
    finally:
        settings.database_url = original_database_url

    test_engine = create_engine(
        settings.test_database_url,
        connect_args={"options": "-c timezone=UTC"},
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(engine: Engine) -> None:
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE trades, positions, market_prices RESTART IDENTITY"))


@pytest.fixture
def session(engine: Engine) -> Session:
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(engine: Engine) -> TestClient:
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
