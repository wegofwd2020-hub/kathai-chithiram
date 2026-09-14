#!/usr/bin/env bash
# Live smoke test of a generation provider behind the wegofwd-llm seam.
# SYNTHETIC data only. Keys are read from ~/.secrets/wegofwd.env (never on the CLI):
#   bash provider_smoke_test.sh gemini
#   bash provider_smoke_test.sh qwen
# ~/.secrets/wegofwd.env should `export GEMINI_API_KEY` / `QWEN_API_KEY` / `QWEN_BASE_URL`.
set -euo pipefail

REPO="/home/sivam/Documents/AIStuff/wegofwd2020-hub/kathai-chithiram"
PROVIDER="${1:-gemini}"
SECRETS="$HOME/.secrets/wegofwd.env"

# Load machine-local secrets (keys live here, never in the repo or on the CLI).
if [ -f "$SECRETS" ]; then
  # shellcheck disable=SC1091
  . "$SECRETS"
else
  echo "note: $SECRETS not found — put your provider key exports there (see header)." >&2
fi

# Qwen needs an OpenAI-compatible base URL; default to DashScope international if
# ~/.secrets did not set one.
export QWEN_BASE_URL="${QWEN_BASE_URL:-https://dashscope-intl.aliyuncs.com/compatible-mode/v1}"

# Grounding (KC-21): point at the ingested corpus so generation is grounded in cited
# passages (the CLI pseudonymises the story before querying it). Absent corpus -> the
# pipeline simply degrades to ungrounded generation.
export KC_ARIVU_DB="${KC_ARIVU_DB:-$(dirname "$REPO")/wegofwd-arivu/tier1.corpus.db}"
if [ -f "$KC_ARIVU_DB" ]; then
  echo "grounding: ON (corpus present)"
else
  echo "grounding: off (no corpus at $KC_ARIVU_DB)"
fi

# A synthetic story (no real child) written to a private temp file.
STORY="$(mktemp)"
trap 'rm -f "$STORY"' EXIT
cat > "$STORY" <<'STORYEOF'
Milo is getting ready for his first visit to the dentist. He feels a little nervous.
Mum shows him the toothbrush and they practice opening wide. At the clinic, the dentist
counts Milo's teeth one by one. Milo sits calmly and does a great job. Afterwards he gets
a sticker and smiles.
STORYEOF

cd "$REPO"
echo "== provider: $PROVIDER (synthetic data) =="
.venv/bin/python -m kathai_chithiram.cli generate \
  --provider "$PROVIDER" --synthetic-data --no-render \
  --child-name Milo "$STORY"
