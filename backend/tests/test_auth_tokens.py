"""JWT helpers use PyJWT (no python-ecdsa / python-jose)."""

from uuid import uuid4

from app.auth.security import create_access_token, decode_access_token


def test_access_token_round_trip():
    user_id = uuid4()
    token = create_access_token(user_id, remember_me=True)
    data = decode_access_token(token)
    assert data.user_id == user_id


def test_access_token_rejects_tampered_token():
    token = create_access_token(uuid4(), remember_me=False)
    data = decode_access_token(token + "x")
    assert data.user_id is None


def test_access_token_rejects_garbage():
    assert decode_access_token("not-a-jwt").user_id is None
