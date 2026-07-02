"""Tests for registration invite codes."""

from app.services.registration_invites import _format_code, _normalize_code, generate_invite_code


def test_normalize_code_strips_dashes_and_case():
    assert _normalize_code("abcd-efgh") == "ABCDEFGH"
    assert _normalize_code("  abcd efgh  ") == "ABCDEFGH"


def test_format_code_groups_long_codes():
    assert _format_code("ABCDEFGH1234") == "ABCD-EFGH-1234"


def test_generate_invite_code_has_expected_shape():
    code = generate_invite_code()
    assert len(_normalize_code(code)) == 12
    assert "-" in code
