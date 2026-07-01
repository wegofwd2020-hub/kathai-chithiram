# KC-6 — Zero-retention / no-training provider key + request enforcement

**Labels:** P0, privacy, security
**Status:** ✅ Done (2026-07-01) — Confirmed via the claude-api reference that Anthropic's no-training / zero-retention posture is an **organization-level** configuration of the account a key belongs to, **not a per-request header** (a ZDR-misconfigured org simply gets 400s). So the enforcement surface is the *credential*: `anthropic_provider.py` gains an isolated `api_key` param + `build_zdr_provider()` that reads a dedicated `ANTHROPIC_ZDR_API_KEY` and **fails closed** (`ProviderConfigError`) if absent — never falling back to the ambient `ANTHROPIC_API_KEY`. CLI resolves the ZDR key for every real run and records the key class in the audit id (`anthropic:<model>:zdr-key`). 4 new tests; ruff + mypy clean.
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
