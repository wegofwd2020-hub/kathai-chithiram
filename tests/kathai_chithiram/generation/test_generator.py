"""Tests for the scene-script generation orchestrator.

Drives :func:`generate_scene_script` with a scripted stub provider (no network,
no real LLM) to prove the contract: it returns only validated scripts, repairs
invalid replies by feeding the failure back, records one audit entry per
attempt, gives up after the budget, and never lets the child's real name reach
the provider (the seam strips it).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest

from kathai_chithiram.errors import SceneScriptGenerationError
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT, generate_scene_script
from kathai_chithiram.privacy import NameMapping
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse, ProviderConfig

COMPLIANT = ProviderConfig(provider_id="stub:no-train-zdr", no_training=True, zero_retention=True)

# A fictional child whose name must never appear in the outbound payload.
MOCK_CHILD_NAME = "Robin"
MOCK_STORY = "Robin is nervous about the slide. When Robin tries it, Robin smiles."


@dataclass
class ScriptedProvider:
    """A fake provider that replies with a fixed sequence of canned texts.

    Records every request so a test can inspect the outbound (pseudonymized)
    prompt and the per-attempt system prompts. Once the scripted replies run
    out, it repeats the last one.
    """

    replies: list[str]
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.replies) - 1)
        return LLMResponse(text=self.replies[index])


def _mapping() -> NameMapping:
    return NameMapping.for_child(MOCK_CHILD_NAME)


def _valid_script() -> dict[str, Any]:
    return copy.deepcopy(EXAMPLE_SCENE_SCRIPT)


def _invalid_script() -> dict[str, Any]:
    # Break the caption==narration cross-field rule on the first scene.
    script = _valid_script()
    script["scenes"][0]["caption"] = "something that does not match the narration"
    return script


def _clock() -> datetime:
    return datetime(2026, 6, 30, tzinfo=timezone.utc)


def test_valid_first_attempt_returns_validated_script() -> None:
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
        clock=_clock,
    )
    assert result.attempts == 1
    assert len(result.records) == 1
    assert result.records[0].request_id == "req-1#1"
    assert result.script["title"] == EXAMPLE_SCENE_SCRIPT["title"]


def test_json_wrapped_in_fences_and_prose_is_parsed() -> None:
    fenced = f"Here is the scene script:\n```json\n{json.dumps(_valid_script())}\n```\nDone."
    provider = ScriptedProvider(replies=[fenced])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.attempts == 1


def test_repair_reuses_a_byte_identical_cacheable_prefix() -> None:
    # KC-12: across a repair, the static prefix is byte-identical (cacheable) and
    # only the volatile feedback suffix changes.
    provider = ScriptedProvider(
        replies=[json.dumps(_invalid_script()), json.dumps(_valid_script())]
    )
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
        clock=_clock,
    )
    assert result.attempts == 2
    first, second = provider.requests
    assert first.system_prefix and first.system_prefix == second.system_prefix
    assert first.system_prompt.startswith(first.system_prefix)
    assert second.system_prompt.startswith(second.system_prefix)
    # First attempt carries no volatile suffix; the repair adds only the feedback.
    assert first.system_prompt == first.system_prefix
    suffix = second.system_prompt[len(second.system_prefix) :]
    assert "scene.caption.mismatch" in suffix
    assert len(suffix) < len(second.system_prefix)


def test_invalid_then_valid_repairs_with_feedback() -> None:
    provider = ScriptedProvider(
        replies=[json.dumps(_invalid_script()), json.dumps(_valid_script())]
    )
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.attempts == 2
    assert len(result.records) == 2
    assert [r.request_id for r in result.records] == ["req-1#1", "req-1#2"]
    # First attempt had no repair feedback; the second one did.
    assert "previous attempt was rejected" not in provider.requests[0].system_prompt
    assert "previous attempt was rejected" in provider.requests[1].system_prompt
    assert "scene.caption.mismatch" in provider.requests[1].system_prompt


def test_unparseable_then_valid_repairs() -> None:
    provider = ScriptedProvider(replies=["not json at all", json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.attempts == 2
    assert "emit exactly one" in provider.requests[1].system_prompt


def test_exhausts_attempts_on_persistent_invalid() -> None:
    provider = ScriptedProvider(replies=[json.dumps(_invalid_script())])
    with pytest.raises(SceneScriptGenerationError) as exc:
        generate_scene_script(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=provider,
            config=COMPLIANT,
            request_id="req-1",
            max_attempts=2,
        )
    assert exc.value.rule == "generation.exhausted"
    assert exc.value.attempts == 2
    assert len(provider.requests) == 2


def test_exhausts_attempts_on_persistent_garbage() -> None:
    provider = ScriptedProvider(replies=["definitely not json"])
    with pytest.raises(SceneScriptGenerationError) as exc:
        generate_scene_script(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=provider,
            config=COMPLIANT,
            request_id="req-1",
            max_attempts=3,
        )
    assert exc.value.rule == "generation.exhausted"
    assert len(provider.requests) == 3


def test_child_name_never_reaches_provider() -> None:
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    sent = provider.requests[0].prompt
    assert MOCK_CHILD_NAME not in sent
    assert "CHILD" in sent  # the token took its place


def test_blank_request_id_rejected() -> None:
    with pytest.raises(ValueError, match="request_id"):
        generate_scene_script(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
            config=COMPLIANT,
            request_id="  ",
        )


def test_non_positive_max_attempts_rejected() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        generate_scene_script(
            story_text=MOCK_STORY,
            mapping=_mapping(),
            provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
            config=COMPLIANT,
            request_id="req-1",
            max_attempts=0,
        )


def test_generation_constrains_output_to_v2_schema() -> None:
    from kathai_chithiram.scene_script.schema import SCENE_SCRIPT_SCHEMA_V2

    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert provider.requests[0].output_schema == SCENE_SCRIPT_SCHEMA_V2


from dataclasses import dataclass as _dataclass  # noqa: E402
from dataclasses import field as _field  # noqa: E402

from kathai_chithiram.generation.grounding import GroundingPassage  # noqa: E402


@_dataclass
class FakeGroundingSource:
    passages: list[GroundingPassage]
    queries: list[str] = _field(default_factory=list)

    def retrieve(self, query: str, *, limit: int = 5) -> list[GroundingPassage]:
        self.queries.append(query)
        return list(self.passages)


def test_grounding_injects_block_and_records_source_ids() -> None:
    passages = [
        GroundingPassage(text="warm up to the brush", source_id="cdc:oral-1", licence_ref="cdc:pd"),
        GroundingPassage(
            text="use a visual schedule", source_id="cdc:oral-1", licence_ref="cdc:pd"
        ),
        GroundingPassage(
            text="first dental visit tips", source_id="ed:idea-2", licence_ref="ed:pd"
        ),
    ]
    grounding = FakeGroundingSource(passages)
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
        grounding=grounding,
    )
    # source ids recorded, de-duplicated, order-preserving
    assert result.grounding_source_ids == ("cdc:oral-1", "ed:idea-2")
    # the cited block reached the system prompt
    assert "cdc:oral-1" in provider.requests[0].system_prompt
    assert "REFERENCE PRACTICE" in provider.requests[0].system_prompt


def test_grounding_query_is_pseudonymised() -> None:
    grounding = FakeGroundingSource([])
    generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
        config=COMPLIANT,
        request_id="req-1",
        grounding=grounding,
    )
    assert grounding.queries, "grounding was queried"
    q = grounding.queries[0]
    assert MOCK_CHILD_NAME not in q          # real name never sent to the corpus
    assert "CHILD" in q                       # the token took its place


def test_no_grounding_leaves_prompt_and_ids_unchanged() -> None:
    provider = ScriptedProvider(replies=[json.dumps(_valid_script())])
    result = generate_scene_script(
        story_text=MOCK_STORY,
        mapping=_mapping(),
        provider=provider,
        config=COMPLIANT,
        request_id="req-1",
    )
    assert result.grounding_source_ids == ()
    assert "REFERENCE PRACTICE" not in provider.requests[0].system_prompt
