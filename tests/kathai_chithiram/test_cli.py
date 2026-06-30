"""Tests for the end-to-end CLI.

Driven with a scripted stub provider and ``--no-render`` so the wiring is
exercised without a network call or a heavy matplotlib render. The privacy and
review boundaries are the focus: the raw story (with the name) is stored, the
scene script is not (token only), the name never reaches the provider, and the
provider's privacy posture must be asserted before anything is sent.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from kathai_chithiram.cli import main
from kathai_chithiram.generation import EXAMPLE_SCENE_SCRIPT
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

CHILD = "Robin"
STORY = "Robin is scared of the dark. Robin turns on a light and feels calm."


@dataclass
class ScriptedProvider:
    """A fake provider returning one canned JSON reply, recording requests."""

    reply: str
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.reply)


def _provider() -> ScriptedProvider:
    return ScriptedProvider(reply=json.dumps(copy.deepcopy(EXAMPLE_SCENE_SCRIPT)))


def _write_story(tmp_path: Path) -> Path:
    story_file = tmp_path / "story.txt"
    story_file.write_text(STORY, encoding="utf-8")
    return story_file


def _argv(story_file: Path, store_root: Path, *extra: str) -> list[str]:
    return [
        str(story_file),
        "--child-name",
        CHILD,
        "--story-id",
        "test-story",
        "--store-root",
        str(store_root),
        *extra,
    ]


def test_happy_path_stores_story_and_scene_script(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    code = main(
        _argv(_write_story(tmp_path), store_root, "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    assert code == 0

    story_dir = store_root / "test-story"
    # The raw story (which names the child) is stored as story.txt by design.
    assert (story_dir / "story.txt").read_text(encoding="utf-8") == STORY
    # The scene script must carry only the token — never the real name.
    script_text = (story_dir / "scene_script.json").read_text(encoding="utf-8")
    assert CHILD not in script_text
    assert "CHILD" in json.loads(script_text)["child_token"]


def test_child_name_never_reaches_provider(tmp_path: Path) -> None:
    provider = _provider()
    main(
        _argv(_write_story(tmp_path), tmp_path / "store", "--provider-no-train-zdr", "--no-render"),
        provider=provider,
    )
    sent = provider.requests[0].prompt
    assert CHILD not in sent
    assert "CHILD" in sent


def test_refuses_without_privacy_assertion(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    provider = _provider()
    # No --provider-no-train-zdr: generation must refuse before dispatch.
    code = main(
        _argv(_write_story(tmp_path), store_root, "--no-render"),
        provider=provider,
    )
    assert code == 2
    assert provider.requests == []  # nothing was sent
    assert not (store_root / "test-story").exists()  # nothing was stored


def test_missing_story_file_errors(tmp_path: Path) -> None:
    code = main(
        _argv(tmp_path / "does-not-exist.txt", tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2


def test_empty_story_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    code = main(
        _argv(empty, tmp_path / "store", "--provider-no-train-zdr"),
        provider=_provider(),
    )
    assert code == 2
