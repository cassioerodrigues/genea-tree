from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    pwd = "super-secret-password"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_round_trip() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_round_trip() -> None:
    token, jti = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"
    assert payload["jti"] == jti


def test_decode_token_rejects_invalid_signature() -> None:
    bad = jwt.encode({"sub": "x"}, "other-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(ValueError):
        decode_token(bad)


def test_access_token_expires() -> None:
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError):
        decode_token(token)
