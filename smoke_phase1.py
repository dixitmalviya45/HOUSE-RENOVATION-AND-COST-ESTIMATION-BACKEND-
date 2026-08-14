"""
Phase 1 smoke test — auth crypto + API routes (DB mocked).

Run from backend/:  python smoke_phase1.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_and_jwt() -> None:
    hashed = hash_password("securepass1")
    assert verify_password("securepass1", hashed)
    assert not verify_password("wrong", hashed)
    token = create_access_token("user-123")
    assert decode_access_token(token)["sub"] == "user-123"
    print("OK  password hashing + JWT")


def test_auth_api() -> None:
    app = create_app()
    stored: dict[str, MagicMock] = {}

    def make_user(full_name: str, email: str, hashed_password: str):
        user = MagicMock()
        user.id = "507f1f77bcf86cd799439011"
        user.full_name = full_name
        user.email = email
        user.hashed_password = hashed_password
        user.created_at = datetime.now(timezone.utc)
        user.insert = AsyncMock(return_value=user)
        stored[email.lower()] = user
        return user

    async def find_one(expression=None, *args, **kwargs):
        email = getattr(expression, "right", None)
        if email is None:
            return None
        return stored.get(str(email).lower())

    async def get_user(user_id: str):
        for user in stored.values():
            if str(user.id) == str(user_id):
                return user
        return None

    mock_user_cls = MagicMock()
    mock_user_cls.side_effect = lambda **kw: make_user(**kw)
    mock_user_cls.find_one = AsyncMock(side_effect=find_one)
    mock_user_cls.get = AsyncMock(side_effect=get_user)
    mock_user_cls.email = SimpleNamespace(
        __eq__=lambda self, other: SimpleNamespace(right=str(other).lower())
    )
    # Proper equality helper for User.email == value
    class _Email:
        def __eq__(self, other):
            return SimpleNamespace(right=str(other).lower())

    mock_user_cls.email = _Email()

    with patch("app.main.init_db", new_callable=AsyncMock):
        with patch("app.api.auth.User", mock_user_cls):
            with patch("app.middleware.auth_middleware.User", mock_user_cls):
                with TestClient(app) as client:
                    health = client.get("/health")
                    assert health.status_code == 200, health.text
                    print("OK  /health")

                    signup = client.post(
                        "/api/auth/signup",
                        json={
                            "full_name": "Test User",
                            "email": "test@example.com",
                            "password": "securepass1",
                        },
                    )
                    assert signup.status_code == 201, signup.text
                    body = signup.json()
                    assert body["access_token"]
                    assert body["user"]["email"] == "test@example.com"
                    print("OK  POST /api/auth/signup")

                    login = client.post(
                        "/api/auth/login",
                        json={"email": "test@example.com", "password": "securepass1"},
                    )
                    assert login.status_code == 200, login.text
                    token = login.json()["access_token"]
                    print("OK  POST /api/auth/login")

                    me = client.get(
                        "/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    assert me.status_code == 200, me.text
                    assert me.json()["full_name"] == "Test User"
                    print("OK  GET /api/auth/me")

                    projects = client.get(
                        "/api/projects",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    assert projects.status_code == 200
                    assert projects.json() == []
                    print("OK  GET /api/projects (Phase 2 stub)")


if __name__ == "__main__":
    test_password_and_jwt()
    test_auth_api()
    print("\nPhase 1 smoke tests passed.")
