"""Tests for read-only API token helpers."""

from app.services.api_tokens import (
    API_TOKEN_PREFIX,
    generate_api_token,
    hash_api_token,
    token_display_prefix,
)


def test_generate_api_token_has_prefix():
    raw = generate_api_token()
    assert raw.startswith(API_TOKEN_PREFIX)
    assert len(raw) > len(API_TOKEN_PREFIX) + 20


def test_hash_api_token_is_stable():
    raw = generate_api_token()
    assert hash_api_token(raw) == hash_api_token(raw)
    assert hash_api_token(raw) != hash_api_token(generate_api_token())


def test_token_display_prefix():
    raw = generate_api_token()
    prefix = token_display_prefix(raw)
    assert prefix.startswith(API_TOKEN_PREFIX)
    assert len(prefix) == len(API_TOKEN_PREFIX) + 8
