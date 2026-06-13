"""The content-safety system prompt for scene-script generation.

Encodes the MUST / MUST-NOT rules of ``docs/CONTENT_SAFETY.md`` §2/§3 as model
instructions — the first of the three enforcement points (§5.1). The prompt also
restates two pipeline invariants the model must honour: never emit a real name
(use the ``CHILD`` token, per PRIVACY.md §6 / KC-2) and emit only a scene script
that conforms to the contract (validated by KC-3 before any rendering).

The rules live as data (:data:`MUST` / :data:`MUST_NOT`) so they can be asserted
in tests and kept in step with the policy doc.
"""

from __future__ import annotations

from kathai_chithiram.privacy.pseudonymize import DEFAULT_CHILD_TOKEN

__all__ = ["MUST", "MUST_NOT", "build_generation_system_prompt"]

#: Positive requirements every generated story must satisfy (CONTENT_SAFETY §2).
MUST: tuple[str, ...] = (
    "Use calm, predictable pacing: short scenes, simple fade/dissolve transitions, "
    "no sudden movement, no flashing or strobing.",
    "Use plain, concrete language: short sentences, literal phrasing, present tense, "
    "one idea per scene; no idioms, sarcasm, or figurative language.",
    "Use positive, supportive framing: show the desired behaviour and a successful "
    "outcome; narrate what to do, not a list of prohibitions.",
    "Keep characters and recurring objects visually consistent from scene to scene.",
    "Caption every scene with text that matches the narration word for word.",
    "Keep audio gentle: even, quiet narration; no loud, sudden, or jarring sounds.",
)

#: Hard prohibitions; any one disqualifies the output (CONTENT_SAFETY §3).
MUST_NOT: tuple[str, ...] = (
    "No frightening, threatening, or distressing imagery or narration "
    "(no violence, injury, punishment, abandonment, monsters, darkness-as-threat).",
    "No flashing, strobing, or rapid scene cuts.",
    "No shaming or negative characterisation of the child (e.g. 'bad', 'naughty').",
    "No medical claims, diagnoses, or therapeutic promises.",
    "No depiction of the child in unsafe acts presented as normal.",
    "No identifying detail beyond the chosen first name; never invent personal facts.",
)


def build_generation_system_prompt(*, child_token: str = DEFAULT_CHILD_TOKEN) -> str:
    """Build the system prompt encoding the content-safety rules.

    Args:
        child_token: The placeholder the model must use in place of any real
            name. Defaults to the pipeline's ``CHILD`` token.

    Returns:
        A system-prompt string listing the MUST and MUST-NOT rules plus the
        pipeline invariants (token usage and contract-conformant output).
    """
    must_lines = "\n".join(f"- {rule}" for rule in MUST)
    must_not_lines = "\n".join(f"- {rule}" for rule in MUST_NOT)
    return (
        "You write social stories: calm, predictable, visual narratives that help a "
        "child with special needs understand a situation or routine. The output is "
        "watched by that child, so the bar is high.\n\n"
        "You MUST:\n"
        f"{must_lines}\n\n"
        "You MUST NOT:\n"
        f"{must_not_lines}\n\n"
        "If a parent's story describes a distressing situation, transform it into a "
        "supportive, resolution-oriented story; never reproduce distress for its own "
        "sake. If the request falls outside helping the child understand a situation, "
        "or suggests risk of harm, do not generate a story.\n\n"
        f"Never write a real name. Refer to the child only as '{child_token}'.\n"
        "Emit only a scene script that conforms to the scene-script contract; emit "
        "nothing else."
    )
