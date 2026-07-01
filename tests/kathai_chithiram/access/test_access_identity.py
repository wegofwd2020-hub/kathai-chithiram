"""Tests for the identity seam (ADR-004 Decision 3)."""

from __future__ import annotations

import pytest

from kathai_chithiram.access import IdentityProvider, LocalIdentityProvider, Principal
from kathai_chithiram.errors import AccessDeniedError


def test_local_provider_authenticates_known_credential() -> None:
    provider = LocalIdentityProvider({"tok-abc": Principal("family-1")})
    assert provider.authenticate("tok-abc") == Principal("family-1")


def test_local_provider_fails_closed_on_unknown_credential() -> None:
    provider = LocalIdentityProvider({"tok-abc": Principal("family-1")})
    with pytest.raises(AccessDeniedError, match="unknown or empty credential"):
        provider.authenticate("tok-wrong")


def test_local_provider_fails_closed_on_empty_credential() -> None:
    provider = LocalIdentityProvider({"tok-abc": Principal("family-1")})
    with pytest.raises(AccessDeniedError):
        provider.authenticate("")


def test_local_provider_copies_credentials_defensively() -> None:
    creds = {"tok-abc": Principal("family-1")}
    provider = LocalIdentityProvider(creds)
    creds["tok-xyz"] = Principal("intruder-1")  # must not become authenticatable
    with pytest.raises(AccessDeniedError):
        provider.authenticate("tok-xyz")


def test_local_provider_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="credential token must be non-empty"):
        LocalIdentityProvider({"": Principal("family-1")})


def test_local_provider_satisfies_the_protocol() -> None:
    provider = LocalIdentityProvider({"t": Principal("p1")})
    assert isinstance(provider, IdentityProvider)
