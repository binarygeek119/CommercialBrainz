"""Tests for edit vote create schema."""

import pytest
from pydantic import ValidationError

from app.schemas import VoteCreate


def test_vote_create_accepts_yes_no_abstain():
    assert VoteCreate(choice="yes").choice == "yes"
    assert VoteCreate(choice="no").choice == "no"
    assert VoteCreate(choice="abstain").choice == "abstain"


def test_vote_create_accepts_null_to_clear():
    assert VoteCreate(choice=None).choice is None
    assert VoteCreate().choice is None


def test_vote_create_rejects_invalid_choice():
    with pytest.raises(ValidationError):
        VoteCreate(choice="maybe")
