"""Tests for the parent-facing privacy notice (KC-8)."""

from __future__ import annotations

from pathlib import Path

from kathai_chithiram.intake import (
    PRIVACY_NOTICE_DOC,
    PRIVACY_NOTICE_SUMMARY,
    PRIVACY_NOTICE_VERSION,
    format_notice_preamble,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_version_is_set() -> None:
    assert PRIVACY_NOTICE_VERSION.strip()


def test_summary_names_the_core_commitments() -> None:
    joined = " ".join(PRIVACY_NOTICE_SUMMARY).lower()
    # The commitments a parent most needs to see before consenting.
    assert "train" in joined  # no-training
    assert "delete" in joined  # retention / right to delete
    assert "review" in joined  # human-review gate
    assert "first name" in joined  # minimization


def test_preamble_includes_version_and_doc_pointer() -> None:
    preamble = format_notice_preamble()
    assert PRIVACY_NOTICE_VERSION in preamble
    assert PRIVACY_NOTICE_DOC in preamble
    # Every summarized point is surfaced.
    for point in PRIVACY_NOTICE_SUMMARY:
        assert point in preamble


def test_full_notice_doc_exists_and_matches_version() -> None:
    notice = _REPO_ROOT / PRIVACY_NOTICE_DOC
    assert notice.is_file()
    # The doc's version header and the code constant must not drift.
    assert PRIVACY_NOTICE_VERSION in notice.read_text(encoding="utf-8")
