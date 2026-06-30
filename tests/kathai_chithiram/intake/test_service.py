"""Tests for submit_intake: consent gate -> generate -> store (with consent record)."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kathai_chithiram.errors import ConsentError
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT
from kathai_chithiram.intake import Consent, ParentSubmission, submit_intake
from kathai_chithiram.storage import StoryArtifactStore
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

CHILD = "Robin"
STORY = "Robin is scared of the dark. Robin turns on a light and feels calm."


@dataclass
class ScriptedProvider:
    reply: str
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.reply)


def _provider() -> ScriptedProvider:
    return ScriptedProvider(reply=json.dumps(copy.deepcopy(EXAMPLE_SCENE_SCRIPT)))


def _store(tmp_path: Path) -> StoryArtifactStore:
    return StoryArtifactStore(tmp_path / "store")


def _full_consent() -> Consent:
    return Consent(is_guardian=True, ai_processing=True, human_review_ack=True)


def _submission(story: str = STORY, name: str = CHILD) -> ParentSubmission:
    return ParentSubmission(story_text=story, child_first_name=name, consent=_full_consent())


def _clock() -> datetime:
    return datetime(2026, 6, 30, tzinfo=timezone.utc)


def test_happy_path_stores_story_script_and_consent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    provider = _provider()
    result = submit_intake(
        _submission(),
        provider=provider,
        store=store,
        story_id="intake-1",
        clock=_clock,
    )
    assert result.story_id == "intake-1"
    assert result.generated.attempts == 1

    story_dir = store.story_dir("intake-1")
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY  # raw, with name
    assert CHILD not in (story_dir / "scene_script.json").read_text(encoding="utf-8")

    intake = json.loads((story_dir / "intake.json").read_text(encoding="utf-8"))
    assert intake["consent"] == {
        "is_guardian": True,
        "ai_processing": True,
        "human_review_ack": True,
    }
    assert intake["recorded_at"] == _clock().isoformat()
    assert intake["provider_posture"]["no_training"] is True
    assert intake["provider_posture"]["zero_retention"] is True
    # The consent record carries no story text or name.
    assert CHILD not in json.dumps(intake)
    assert "dark" not in json.dumps(intake)


def test_name_stripped_before_provider(tmp_path: Path) -> None:
    provider = _provider()
    submit_intake(_submission(), provider=provider, store=_store(tmp_path), story_id="intake-1")
    sent = provider.requests[0].prompt
    assert CHILD not in sent
    assert "CHILD" in sent


def test_declined_consent_raises_and_stores_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    provider = _provider()
    submission = ParentSubmission(
        story_text=STORY,
        child_first_name=CHILD,
        consent=Consent(is_guardian=True, ai_processing=False, human_review_ack=True),
    )
    with pytest.raises(ConsentError) as exc:
        submit_intake(submission, provider=provider, store=store, story_id="intake-1")
    assert "ai_processing" in str(exc.value)
    assert provider.requests == []  # nothing generated
    assert not store.exists("intake-1")  # nothing stored


def test_warnings_are_returned_and_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = submit_intake(
        _submission(story="We live at 42 Oak Street. Robin is calm there."),
        provider=_provider(),
        store=store,
        story_id="intake-1",
    )
    assert any("address" in w.lower() for w in result.warnings)
    intake = json.loads((store.story_dir("intake-1") / "intake.json").read_text(encoding="utf-8"))
    assert intake["minimization_warnings"] == list(result.warnings)
