from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture()
def session():
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    engine = create_engine(f"sqlite:///{handle.name}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        yield session
    engine.dispose()
    os.unlink(handle.name)
