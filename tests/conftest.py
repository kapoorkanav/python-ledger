import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "postgresql://ledger_user:ledger_pass@localhost:5432/ledger_db"

engine=create_engine(TEST_DATABASE_URL)
TestingSessionLocal=sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db_session():
    connection=engine.connect()
    transaction=connection.begin()
    session=TestingSessionLocal(bind=connection)

    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db]=override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()