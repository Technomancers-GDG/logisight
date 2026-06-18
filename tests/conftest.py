from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base


@pytest.fixture
def db_session() -> Generator[Session, Any, None]:
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> Generator[TestClient, Any, None]:
    from main import app

    with TestClient(app) as c:
        yield c
