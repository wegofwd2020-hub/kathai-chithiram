"""Synthetic story + test doubles for the wegofwd-llm seam.

The child name ("Milo") and story are fictional synthetic test data
(CLAUDE.md: no real child data in fixtures).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kathai_chithiram.wegofwd_llm.provider import LLMRequest, LLMResponse

#: A synthetic parent story that mentions the child's name several times.
MOCK_STORY = (
    "Milo gets nervous at the dentist. When Milo sits in the chair, Milo can "
    "hold the toy. Milo's mom is there. Milo will be okay."
)

#: The fictional child name used throughout these tests.
MOCK_CHILD_NAME = "Milo"


@dataclass
class CapturingProvider:
    """A fake :class:`LLMProvider` that records the exact request it received.

    Lets a test inspect the *outbound payload* to prove no identifier leaves the
    seam. Returns a fixed canned response.
    """

    reply: str = "ok"
    requests: list[LLMRequest] = field(default_factory=list)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a canned response.

        Args:
            request: The request handed over by the seam.

        Returns:
            A fixed :class:`LLMResponse`.
        """
        self.requests.append(request)
        return LLMResponse(text=self.reply)


@dataclass
class ExplodingProvider:
    """A fake provider that fails if ever called — proving the seam never dispatched."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Raise unconditionally.

        Args:
            request: Ignored.

        Raises:
            AssertionError: Always; the seam should not have reached a provider.
        """
        raise AssertionError("provider was called but dispatch should have been blocked")
