"""Tests for the principal/role model and the deny-by-default policy (ADR-004)."""

from __future__ import annotations

import pytest

from kathai_chithiram.access import (
    AccessPolicy,
    Action,
    ChildGrants,
    Principal,
    Role,
    StoryGrants,
)
from kathai_chithiram.errors import AccessDeniedError

_OWNER = Principal("family-1")
_REVIEWER = Principal("rev-1")
_THERAPIST = Principal("ther-1")
_STRANGER = Principal("nobody-1")


def _grants() -> StoryGrants:
    return StoryGrants(
        owner_id=_OWNER.principal_id,
        assignments={
            _REVIEWER.principal_id: Role.REVIEWER,
            _THERAPIST.principal_id: Role.THERAPIST,
        },
    )


# --- Principal / StoryGrants -----------------------------------------------


def test_principal_rejects_unsafe_id() -> None:
    with pytest.raises(ValueError, match="principal_id"):
        Principal("has space")


def test_grants_role_of_owner_and_assignees() -> None:
    grants = _grants()
    assert grants.role_of(_OWNER) is Role.FAMILY_OWNER
    assert grants.role_of(_REVIEWER) is Role.REVIEWER
    assert grants.role_of(_THERAPIST) is Role.THERAPIST
    assert grants.role_of(_STRANGER) is None


def test_grants_reject_family_owner_as_assignment() -> None:
    with pytest.raises(ValueError, match="not an assignable role"):
        StoryGrants(owner_id="family-1", assignments={"x": Role.FAMILY_OWNER})


def test_grants_reject_owner_also_assigned() -> None:
    with pytest.raises(ValueError, match="owner must not also appear"):
        StoryGrants(owner_id="family-1", assignments={"family-1": Role.REVIEWER})


# --- AccessPolicy.is_allowed -----------------------------------------------


def test_stranger_is_denied_everything() -> None:
    policy, grants = AccessPolicy(), _grants()
    for action in Action:
        assert policy.is_allowed(_STRANGER, grants, action) is False


def test_owner_can_manage_and_write_but_not_decide_suggestions() -> None:
    policy, grants = AccessPolicy(), _grants()
    assert policy.is_allowed(_OWNER, grants, Action.MANAGE_STORY)
    assert policy.is_allowed(_OWNER, grants, Action.WRITE_FEEDBACK)
    assert policy.is_allowed(_OWNER, grants, Action.READ_CONTENT)
    # Premise/suggestion domain is therapist-owned (BRAND §7 / ADR-002).
    assert policy.is_allowed(_OWNER, grants, Action.DECIDE_SUGGESTION) is False


def test_reviewer_scope_is_read_and_review_only() -> None:
    policy, grants = AccessPolicy(), _grants()
    assert policy.is_allowed(_REVIEWER, grants, Action.READ_CONTENT)
    assert policy.is_allowed(_REVIEWER, grants, Action.WRITE_REVIEW)
    assert policy.is_allowed(_REVIEWER, grants, Action.READ_FEEDBACK) is False
    assert policy.is_allowed(_REVIEWER, grants, Action.MANAGE_STORY) is False


def test_therapist_scope_is_feedback_and_suggestions() -> None:
    policy, grants = AccessPolicy(), _grants()
    assert policy.is_allowed(_THERAPIST, grants, Action.READ_FEEDBACK)
    assert policy.is_allowed(_THERAPIST, grants, Action.DECIDE_SUGGESTION)
    assert policy.is_allowed(_THERAPIST, grants, Action.READ_CONTENT)
    assert policy.is_allowed(_THERAPIST, grants, Action.WRITE_REVIEW) is False


# --- AccessPolicy.authorize ------------------------------------------------


def test_authorize_returns_role_on_success() -> None:
    assert AccessPolicy().authorize(
        _REVIEWER, _grants(), Action.WRITE_REVIEW, story_id="s1"
    ) is Role.REVIEWER


def test_authorize_denies_unrelated_principal_with_context() -> None:
    with pytest.raises(AccessDeniedError) as exc:
        AccessPolicy().authorize(_STRANGER, _grants(), Action.READ_CONTENT, story_id="s1")
    assert exc.value.principal_id == "nobody-1"
    assert exc.value.story_id == "s1"
    assert exc.value.action == "read_content"


def test_authorize_denies_wrong_action_for_role() -> None:
    with pytest.raises(AccessDeniedError, match="does not grant this action"):
        AccessPolicy().authorize(_REVIEWER, _grants(), Action.DECIDE_SUGGESTION, story_id="s1")


def test_access_denied_error_message_carries_no_content() -> None:
    err = AccessDeniedError("read_content", "no role", principal_id="p1", story_id="s1")
    text = str(err)
    assert "p1" in text and "s1" in text and "read_content" in text


# ── child-scoped grants (ADR-005 D3) ──────────────────────────────────────────────
def _child_grants() -> ChildGrants:
    return ChildGrants(
        child_id="child-1",
        family_member_ids=frozenset({"mum-1", "dad-1"}),
        assignments={_THERAPIST.principal_id: Role.THERAPIST},
    )


def test_child_grants_resolve_roles() -> None:
    grants = _child_grants()
    assert grants.role_of(Principal("mum-1")) is Role.FAMILY_OWNER  # every parent owns
    assert grants.role_of(Principal("dad-1")) is Role.FAMILY_OWNER
    assert grants.role_of(_THERAPIST) is Role.THERAPIST
    assert grants.role_of(_STRANGER) is None


def test_policy_works_on_child_grants() -> None:
    policy, grants = AccessPolicy(), _child_grants()
    # A parent owns the child's content; a therapist assigned to the child may read it.
    assert policy.is_allowed(Principal("dad-1"), grants, Action.MANAGE_STORY)
    assert policy.is_allowed(_THERAPIST, grants, Action.READ_FEEDBACK)
    assert not policy.is_allowed(_THERAPIST, grants, Action.WRITE_CONTENT)
    with pytest.raises(AccessDeniedError):
        policy.authorize(_STRANGER, grants, Action.READ_CONTENT, story_id="child-1")


def test_child_grants_reject_a_member_who_is_also_an_assignee() -> None:
    with pytest.raises(ValueError, match="must not also be an assignee"):
        ChildGrants(
            child_id="child-1",
            family_member_ids=frozenset({"mum-1"}),
            assignments={"mum-1": Role.THERAPIST},
        )


def test_child_grants_need_a_family_member() -> None:
    with pytest.raises(ValueError, match="at least one family member"):
        ChildGrants(child_id="child-1", family_member_ids=frozenset(), assignments={})
