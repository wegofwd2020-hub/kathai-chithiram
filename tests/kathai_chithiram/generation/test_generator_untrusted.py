"""generate_scene_script threads the synthetic-data escape into the gateway."""

from __future__ import annotations

import json

import pytest

# Reuse the repo's scene-script test helpers if present; otherwise a minimal valid
# script JSON string. Read tests/kathai_chithiram/generation/test_generator.py for the
# canonical _valid_script() helper and ScriptedProvider, and import/copy them here.
from tests.kathai_chithiram.generation.test_generator import (  # type: ignore
    ScriptedProvider,
    _mapping,
    _valid_script,
)

from kathai_chithiram.errors import ProviderConfigError
from kathai_chithiram.generation.generator import generate_scene_script
from kathai_chithiram.wegofwd_llm.provider import ProviderConfig

_NONCOMPLIANT = ProviderConfig(provider_id="qwen:test", no_training=False, zero_retention=False)


def test_untrusted_refused_by_default() -> None:
    with pytest.raises(ProviderConfigError):
        generate_scene_script(
            story_text="a synthetic story",
            mapping=_mapping(),
            provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
            config=_NONCOMPLIANT,
            request_id="req-1",
        )


def test_untrusted_allowed_with_flag() -> None:
    result = generate_scene_script(
        story_text="a synthetic story",
        mapping=_mapping(),
        provider=ScriptedProvider(replies=[json.dumps(_valid_script())]),
        config=_NONCOMPLIANT,
        request_id="req-1",
        allow_untrusted_provider=True,
    )
    assert result.script  # a validated scene script came back
