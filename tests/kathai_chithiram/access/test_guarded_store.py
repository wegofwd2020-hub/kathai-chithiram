"""Tests for the GuardedStore enforcement boundary + store grants plumbing (ADR-004)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.access import (
    AccessOutcome,
    GuardedStore,
    InMemoryAuditSink,
    Principal,
    Role,
)
from kathai_chithiram.errors import AccessDeniedError
from kathai_chithiram.storage import AesGcmCipher, StoryArtifactStore, generate_key

_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)
_OWNER = Principal("family-1")
_REVIEWER = Principal("rev-1")
_THERAPIST = Principal("ther-1")
_STRANGER = Principal("nobody-1")

_SCRIPT = {"schema_version": "1.0", "scenes": []}


def _store(tmp_path: Path, *, encrypted: bool = False) -> StoryArtifactStore:
    cipher = AesGcmCipher(base64.urlsafe_b64decode(generate_key())) if encrypted else None
    return StoryArtifactStore(tmp_path / "store", cipher=cipher)


def _clock() -> datetime:
    return _AT


def _owned_story(
    store: StoryArtifactStore, *, audit: InMemoryAuditSink | None = None
) -> GuardedStore:
    """Create story 's1' owned by _OWNER and return the owner's guarded view."""
    owner_view = GuardedStore(store, _OWNER, audit=audit, clock=_clock)
    owner_view.create_story("s1", created_at=_AT, story_text="a calm story")
    return owner_view


# --- store grants plumbing -------------------------------------------------


def test_store_grants_round_trip_and_absent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_AT, story_text="x")
    assert store.read_grants("s1") is None  # unowned until written
    store.write_grants("s1", {"owner_id": "family-1", "assignments": {"rev-1": "reviewer"}})
    assert store.read_grants("s1") == {
        "owner_id": "family-1",
        "assignments": {"rev-1": "reviewer"},
    }


def test_grants_file_is_swept_by_hard_delete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _owned_story(store)
    grants_path = store.story_dir("s1") / "grants.json"
    assert grants_path.is_file()
    # It sits under the story dir, so the verifiable hard-delete (rmtree + the
    # artifact_paths re-scan) covers it (ADR-004 Decision 4).
    assert grants_path in store.artifact_paths("s1")


# --- ownership bootstrap ---------------------------------------------------


def test_create_story_makes_caller_the_owner(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    assert owner_view.grants("s1").role_of(_OWNER) is Role.FAMILY_OWNER


def test_owner_can_read_and_write_own_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    owner_view.write_scene_script("s1", _SCRIPT)
    assert owner_view.read_scene_script("s1") == _SCRIPT
    assert owner_view.mark_delivered("s1").delivered is True


def test_add_cache_is_a_guarded_content_write(tmp_path: Path) -> None:
    # The video seam persists render provenance via add_cache; it must be
    # authorized like any content write (deny-by-default), not an open side door.
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    path = owner_view.add_cache("s1", "video_provenance.json", b'{"provider":"x"}')
    assert path.is_file()

    with pytest.raises(AccessDeniedError):
        GuardedStore(store, _STRANGER).add_cache("s1", "sneak.json", b"nope")
    assert not (store.story_dir("s1") / "cache" / "sneak.json").exists()


# --- deny-by-default -------------------------------------------------------


def test_stranger_is_denied_and_reads_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _owned_story(store)
    stranger_view = GuardedStore(store, _STRANGER)
    with pytest.raises(AccessDeniedError) as exc:
        stranger_view.read_scene_script("s1")
    assert exc.value.principal_id == "nobody-1"
    assert exc.value.story_id == "s1"


def test_story_without_grants_denies(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_story("s1", created_at=_AT, story_text="x")  # raw store, no owner
    with pytest.raises(AccessDeniedError, match="no access grants"):
        GuardedStore(store, _OWNER).read_scene_script("s1")


def test_authorization_runs_before_decryption(tmp_path: Path) -> None:
    # With a cipher configured, an authorized owner round-trips; an unauthorized
    # principal is denied *before* any decrypt is attempted (AccessDeniedError, not
    # DecryptionError, and no plaintext produced).
    store = _store(tmp_path, encrypted=True)
    owner_view = _owned_story(store)
    owner_view.write_scene_script("s1", _SCRIPT)
    assert owner_view.read_scene_script("s1") == _SCRIPT
    with pytest.raises(AccessDeniedError):
        GuardedStore(store, _STRANGER).read_scene_script("s1")


# --- assignments + scoped roles --------------------------------------------


def test_assigned_reviewer_gets_review_scope_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    owner_view.write_scene_script("s1", _SCRIPT)
    owner_view.assign_role("s1", _REVIEWER.principal_id, Role.REVIEWER)

    reviewer_view = GuardedStore(store, _REVIEWER)
    assert reviewer_view.read_scene_script("s1") == _SCRIPT  # content read allowed
    reviewer_view.write_review_record("s1", {"decision": "approved"})
    with pytest.raises(AccessDeniedError):
        reviewer_view.read_session_feedback("s1")  # feedback is therapist scope


def test_assigned_therapist_gets_feedback_scope_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    owner_view.assign_role("s1", _THERAPIST.principal_id, Role.THERAPIST)

    therapist_view = GuardedStore(store, _THERAPIST)
    assert therapist_view.read_session_feedback("s1") == []  # allowed, empty
    with pytest.raises(AccessDeniedError):
        therapist_view.write_review_record("s1", {"decision": "approved"})


def test_non_owner_cannot_assign_roles(tmp_path: Path) -> None:
    store = _store(tmp_path)
    owner_view = _owned_story(store)
    owner_view.assign_role("s1", _REVIEWER.principal_id, Role.REVIEWER)
    reviewer_view = GuardedStore(store, _REVIEWER)
    with pytest.raises(AccessDeniedError):
        reviewer_view.assign_role("s1", _STRANGER.principal_id, Role.THERAPIST)


# --- audit -----------------------------------------------------------------


def test_audit_records_allow_and_deny_log_safely(tmp_path: Path) -> None:
    store = _store(tmp_path)
    audit = InMemoryAuditSink()
    owner_view = _owned_story(store, audit=audit)  # create_story -> one ALLOWED
    owner_view.write_scene_script("s1", _SCRIPT)  # -> one ALLOWED (write_content)
    owner_view.read_scene_script("s1")  # -> one ALLOWED (read_content)

    stranger_view = GuardedStore(store, _STRANGER, audit=audit, clock=_clock)
    with pytest.raises(AccessDeniedError):
        stranger_view.read_scene_script("s1")  # -> one DENIED

    outcomes = [(e.principal_id, e.action, e.outcome) for e in audit.events()]
    assert ("family-1", "manage_story", AccessOutcome.ALLOWED) in outcomes
    assert ("family-1", "read_content", AccessOutcome.ALLOWED) in outcomes
    assert ("nobody-1", "read_content", AccessOutcome.DENIED) in outcomes
    # Log-safe: records carry opaque ids only, never story text.
    for event in audit.events():
        assert "calm story" not in (event.to_record().get("reason") or "")
        assert event.recorded_at == _AT
