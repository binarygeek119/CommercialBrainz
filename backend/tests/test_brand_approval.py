"""Tests for brand approval voting threshold and moderator vote decisions."""

from uuid import uuid4

from app.models import EditType, UserRole, Vote, VoteChoice
from app.services import EditService


class _FakeEdit:
    edit_type = EditType.CREATE_ADVERTISER


class _FakeVideoEdit:
    edit_type = EditType.CREATE_VIDEO


class _FakeUser:
    def __init__(self, role: UserRole = UserRole.USER, is_auto_editor: bool = False):
        self.id = uuid4()
        self.role = role
        self.is_auto_editor = is_auto_editor


def test_brand_vote_threshold():
    assert EditService._vote_threshold(_FakeEdit()) == 10


def test_video_vote_threshold():
    assert EditService._vote_threshold(_FakeVideoEdit()) == 3


def test_mod_yes_vote_decides_apply():
    mod = _FakeUser(role=UserRole.MOD)
    vote = Vote(edit_id=uuid4(), voter_id=mod.id, choice=VoteChoice.YES)
    assert EditService._mod_vote_decision([vote], {mod.id: mod}) == "apply"


def test_mod_no_vote_decides_reject():
    mod = _FakeUser(role=UserRole.ADMIN)
    vote = Vote(edit_id=uuid4(), voter_id=mod.id, choice=VoteChoice.NO)
    assert EditService._mod_vote_decision([vote], {mod.id: mod}) == "reject"


def test_mod_no_overrides_community_yes():
    mod = _FakeUser(role=UserRole.MOD)
    user = _FakeUser()
    votes = [
        Vote(edit_id=uuid4(), voter_id=user.id, choice=VoteChoice.YES),
        Vote(edit_id=uuid4(), voter_id=mod.id, choice=VoteChoice.NO),
    ]
    voters = {user.id: user, mod.id: mod}
    assert EditService._mod_vote_decision(votes, voters) == "reject"


def test_community_votes_alone_do_not_decide():
    user_a = _FakeUser()
    user_b = _FakeUser()
    votes = [
        Vote(edit_id=uuid4(), voter_id=user_a.id, choice=VoteChoice.YES),
        Vote(edit_id=uuid4(), voter_id=user_b.id, choice=VoteChoice.YES),
        Vote(edit_id=uuid4(), voter_id=user_b.id, choice=VoteChoice.YES),
    ]
    voters = {user_a.id: user_a, user_b.id: user_b}
    assert EditService._mod_vote_decision(votes, voters) is None
