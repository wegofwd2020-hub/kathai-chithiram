"""Tests for the intake submission model: consent gate + minimization advisories."""

from __future__ import annotations

import pytest

from kathai_chithiram.intake import Consent, ParentSubmission, minimization_warnings


def _consent(**overrides: bool) -> Consent:
    base = {"is_guardian": True, "ai_processing": True, "human_review_ack": True}
    base.update(overrides)
    return Consent(**base)


def test_full_consent_is_granted() -> None:
    c = _consent()
    assert c.granted is True
    assert c.missing() == ()


def test_missing_consents_reported_in_order() -> None:
    c = _consent(is_guardian=False, human_review_ack=False)
    assert c.granted is False
    assert c.missing() == ("is_guardian", "human_review_ack")


def test_submission_rejects_blank_story() -> None:
    with pytest.raises(ValueError, match="story_text"):
        ParentSubmission(story_text="   ", child_first_name="Sam", consent=_consent())


def test_submission_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="child_first_name"):
        ParentSubmission(story_text="A story.", child_first_name=" ", consent=_consent())


def test_minimal_submission_has_no_warnings() -> None:
    sub = ParentSubmission(
        story_text="Sam is nervous about the slide. Sam tries it and smiles.",
        child_first_name="Sam",
        consent=_consent(),
    )
    assert minimization_warnings(sub) == []


def test_multi_word_name_warns_about_surname() -> None:
    sub = ParentSubmission(
        story_text="A calm story about the park.",
        child_first_name="Sam Carter",
        consent=_consent(),
    )
    warnings = minimization_warnings(sub)
    assert any("first name" in w for w in warnings)


@pytest.mark.parametrize(
    ("story", "needle"),
    [
        ("Sam was born on 03/14/2019 in the city.", "date of birth"),
        ("Call us at 555 123 4567 if needed.", "phone number"),
        ("We live at 42 Oak Street near the park.", "home address"),
        ("Sam was diagnosed last year and takes 5 mg daily.", "medical"),
    ],
)
def test_oversharing_patterns_warn(story: str, needle: str) -> None:
    sub = ParentSubmission(story_text=story, child_first_name="Sam", consent=_consent())
    warnings = minimization_warnings(sub)
    assert any(needle in w.lower() for w in warnings)
    # Advisory messages never echo the matched text.
    assert all("Oak Street" not in w and "555" not in w for w in warnings)
