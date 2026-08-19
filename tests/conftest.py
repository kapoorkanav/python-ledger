import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
from app.database import get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ledger_user:ledger_pass@localhost:5432/ledger_db"
)
os.environ.setdefault("LEDGER_API_KEY", "test-secret-key")

engine=create_engine(TEST_DATABASE_URL)
TestingSessionLocal=sessionmaker(autocommit=False, autoflush=False, bind=engine, join_transaction_mode="create_savepoint")

@pytest.fixture()
def db_session():
    connection=engine.connect()
    transaction=connection.begin()
    session=TestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db]=override_get_db
    try:
        yield TestClient(app, headers={"X-API-Key": os.environ["LEDGER_API_KEY"]})
    finally:
        app.dependency_overrides.clear()

@pytest.fixture()
def key():
    def _key(label: str="k")->str:
        return f"{label}-{uuid.uuid4()}"
    return _key

@pytest.fixture
def account(client):
    def _account(name: str="Alice", currency: str="USD"):
        return client.post("/accounts", json={"name": name, "currency": currency}).json()
    return _account