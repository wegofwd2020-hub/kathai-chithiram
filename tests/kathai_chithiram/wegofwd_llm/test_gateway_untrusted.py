"""The synthetic-data escape: a non-compliant provider runs only when explicitly allowed."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kathai_chithiram.errors import IdentifierLeakError, ProviderConfigError
from kathai_chithiram.privacy.pseudonymize import NameMapping
from kathai_chithiram.wegofwd_llm.gateway import run_generation
from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse, ProviderConfig

_NONCOMPLIANT = ProviderConfig(provider_id="gemini:test", no_training=False, zero_retention=False)
# NameMapping uses `identifiers: tuple[str, ...]` (not `real_name`); confirmed from source.
_MAPPING = NameMapping(identifiers=("Milo",), token="CHILD")
_STORY = "Milo brushes his teeth. Milo smiles."


@dataclass
class _Capturing:
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text="ok")


def test_noncompliant_refused_by_default() -> None:
    with pytest.raises(ProviderConfigError):
        run_generation(
            story_text=_STORY, mapping=_MAPPING, provider=_Capturing(),
            config=_NONCOMPLIANT, request_id="r1",
        )


def test_noncompliant_allowed_with_flag() -> None:
    provider = _Capturing()
    result = run_generation(
        story_text=_STORY, mapping=_MAPPING, provider=provider,
        config=_NONCOMPLIANT, request_id="r1", allow_untrusted_provider=True,
    )
    assert result.response.text == "ok"
    assert len(provider.requests) == 1
    # posture recorded truthfully
    assert result.record.no_training is False and result.record.zero_retention is False
    # pseudonymised: the child's real name never reaches the provider
    assert "Milo" not in provider.requests[0].prompt
    assert "CHILD" in provider.requests[0].prompt


def test_identifier_hard_stop_still_runs_under_flag() -> None:
    # A mapping whose token does not actually replace the name leaves a residual
    # identifier; the hard-stop must still fire even under the synthetic override.
    # token="MILO" is the uppercase form of the identifier; pseudonymize replaces
    # "Milo"→"MILO" but count_identifiers scans case-insensitively so "MILO"
    # still matches the "Milo" identifier pattern — residual leak detected.
    leaky = NameMapping(identifiers=("Milo",), token="MILO")
    with pytest.raises(IdentifierLeakError):
        run_generation(
            story_text=_STORY, mapping=leaky, provider=_Capturing(),
            config=_NONCOMPLIANT, request_id="r1", allow_untrusted_provider=True,
        )
