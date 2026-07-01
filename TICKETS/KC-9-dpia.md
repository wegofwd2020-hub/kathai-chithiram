# KC-9 — Data Protection Impact Assessment (DPIA)

**Labels:** P1, privacy, compliance
**Refs:** PRIVACY.md §8, §9 ("DPIA before EU launch"); ADR-002 (profiling touchpoint); UK/EU GDPR Art. 35

## Why
Kathai Chithiram processes **special-category, child-related data** (a parent's
story about their child, often a child with a disability) and, with the ADR-002
capture track, **profiling** of that child. Under UK/EU GDPR Art. 35 this
combination all but requires a DPIA *before* any EU/UK launch — PRIVACY.md §8/§9
already commit to one. A DPIA is also the right forcing function to state, in one
place, which risk mitigations are built vs. still open (KC-5 encryption, KC-6
ZDR key) so residual risk is explicit, not implied.

## Acceptance criteria
- A DPIA document exists (`docs/DPIA.md`) covering, at minimum: the processing
  described (nature/scope/context/purpose + data flow), necessity &
  proportionality (lawful basis, minimization, retention), the risks to the data
  subject, the mitigations mapped to the controls actually in the codebase
  (KC-1..KC-8), and residual risk.
- Each mitigation cites its status honestly — built vs. pending — so an unbuilt
  control (KC-5 at-rest encryption, KC-6 ZDR provider key) is not represented as
  in place.
- The ADR-002 profiling data category (per-session feedback) is assessed, not
  just the story pipeline.
- The document is explicit that it is a **draft pending DPO/counsel sign-off**
  and names the preconditions for launch sign-off (incl. the open mitigations).
- PRIVACY.md §9 links to it; the DPIA names a review cadence.

## Implementation notes
- This ticket is an assessment **document**, not code — no source changes and no
  new tests. It is the internal source DPIA; a regulator-facing filing (if ever
  needed) is downstream.
- Keep it consistent with PRIVACY.md and CONTENT_SAFETY.md; where a control is
  referenced, point at the module/ticket that implements it.
- Sign-off (DPO + counsel) and closing the open mitigations are **out of scope**
  for this ticket — it produces the assessment and makes the residual risk and
  the launch preconditions explicit. Actual sign-off is a human gate.
