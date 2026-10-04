from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.service import register_user
from database.base import Base


def test_first_registered_user_becomes_admin_without_seeded_credentials():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()

    try:
        first_user, first_pending = register_user(
            db,
            SimpleNamespace(
                full_name="First User",
                email="first@example.com",
                password="secret123",
                role="investigator",
            ),
        )
        second_user, second_pending = register_user(
            db,
            SimpleNamespace(
                full_name="Second User",
                email="second@example.com",
                password="secret123",
                role="admin",
            ),
        )
        first_role = first_user.role
        second_role = second_user.role
        first_active = first_user.is_active
        second_active = second_user.is_active
    finally:
        db.close()

    assert first_role == "ADMIN"
    assert second_role == "INVESTIGATOR"
    assert first_pending is False
    assert first_active is True
    assert second_pending is True
    assert second_active is False
