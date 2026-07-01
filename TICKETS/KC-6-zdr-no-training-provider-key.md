# KC-6 — Zero-retention / no-training provider key + request enforcement

**Labels:** P0, privacy, security
**Refs:** PRIVACY.md §6, §9; `wegofwd_llm/provider.py`, `anthropic_provider.py`, `gateway.py`

## Why
The provider seam already *records and enforces* a privacy posture:
`ProviderConfig(no_training, zero_retention)` gates dispatch in `gateway.py`
(refuses unless `is_privacy_compliant`), and `intake/service.py` stamps
`no_training=True, zero_retention=True` into `intake.json`. But that posture is
currently a **self-asserted flag** — nothing in the actual API call makes it true.
`anthropic_provider.py` builds `anthropic.Anthropic()` with no arguments (resolves
the ambient `ANTHROPIC_API_KEY`), sets no headers, no org/workspace, and no
retention opt-out. The recorded posture and the wire behaviour can silently
diverge.

## Acceptance criteria
- The concrete provider is constructed with a **dedicated, isolated credential**
  (distinct env var / secret) provisioned against a zero-data-retention +
  no-training configuration — not the ambient developer `ANTHROPIC_API_KEY`.
- Any provider-required headers / workspace / org settings for the ZDR + no-train
  posture are actually set on the client or request.
- The recorded `ProviderConfig` reflects the credential/config actually used; if
  the ZDR key/config is absent, generation **fails closed** (raises), it does not
  fall back to a non-compliant path while still claiming compliance.
- Missing/misconfigured ZDR credential produces a clear domain error at startup or
  first call — never a silent downgrade.
- Provider posture (id + no_training + zero_retention + which key class) remains
  auditable per request via `ProviderRequestRecord` → `intake.json`.

## Implementation notes
- Add a ZDR-key/config parameter to `AnthropicProvider.__init__` and inject into
  the `anthropic.Anthropic(...)` client (api_key, and headers/org if required).
  Read the key from a distinct env var (e.g. `ANTHROPIC_ZDR_API_KEY`).
- Confirm the exact Anthropic no-training / zero-retention mechanism before
  wiring (account/org-level setting vs. header) — check the current provider docs
  via the claude-api skill; record what was used.
- Keep the `wegofwd-llm` seam provider-agnostic: enforcement lives at the gateway,
  credential resolution at the concrete provider.
- Tests: assert the client is built with the dedicated key; assert generation
  raises when the ZDR credential is missing rather than proceeding; assert the
  recorded posture matches the constructed client. Never send real story text to
  a live provider in tests — mock the client.
