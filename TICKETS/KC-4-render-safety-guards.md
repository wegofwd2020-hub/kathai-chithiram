# KC-4 — Render-time seizure-safety guards + content-safety system prompt

**Labels:** P0, safety
**Refs:** docs/CONTENT_SAFETY.md §2/§3/§5

## Acceptance criteria
- Renderers enforce frame-rate, no-flash (>3 Hz) / high-contrast oscillation limits, and audio-level caps.
- The generation system prompt encodes the MUST / MUST-NOT content rules.
- Human review gate remains until KC-3 + KC-4 are tested.
