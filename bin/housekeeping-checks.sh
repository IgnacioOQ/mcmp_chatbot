#!/usr/bin/env bash
#
# housekeeping-checks.sh — the deterministic steps of HOUSEKEEPING.md in one run.
#
# COVERS:
#   Phase 2  Python lint (ruff, pyflakes rules)          [gate]
#   Phase 2  frontend type check (tsc --noEmit)          [gate]
#   Phase 2  frontend lint (next lint)                   [gate]
#   Phase 3  pytest tests/ inside the backend image      [gate]
#   Phase 4  uv.lock in sync with pyproject.toml         [gate]
#   Phase 4  backend image build (the Cloud Run image)   [gate]
#   Phase 4  frontend production build (next build)      [gate]
#   Phase 4  no secrets / generated files tracked        [gate]
#   Phase 4  npm audit (production deps)                 [info]
#   Phase 5  housekeeping_log.jsonl integrity            [gate]
#
# DOES NOT COVER (agent steps in HOUSEKEEPING.md):
#   Phase 1 baseline read · Phase 3 Gemini stress battery (live API, quota) ·
#   Phase 4 live-data freshness (Firestore), docs freshness, open-task review ·
#   Phase 5 Latest Report, log append, task filing, last_checked bump.
#   The scraper image (firebase/scraper/Dockerfile) is not built here.
#
# NEVER RUNS: deploy-backend.sh, deploy-scraper.sh, git push (App Hosting
#   rollout), gcloud/firebase commands, Firestore or Sheets writes.
#
# PYTHON MODE: the lock does not install on every host (chromadb -> onnxruntime
#   has no macOS x86_64 wheel), so Python steps run in the backend image by
#   default. HK_PY_MODE=docker|host overrides; otherwise docker if the daemon
#   answers, else host (.venv). The chosen mode and reason are in the summary.
#
# Exit code: 0 iff every [gate] step passes. [info] and SKIP steps never gate.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || { echo "FATAL: cannot cd to repo root"; exit 2; }

GATE_FAIL=0; SUMMARY=""
IMAGE="mcmp-backend:housekeeping"
FE="firebase/frontend"

record() { SUMMARY+="$(printf '%-16s %-5s %s' "$1" "$2" "$3")"$'\n'; [ "$2" = FAIL ] && GATE_FAIL=1; return 0; }
hdr()    { printf '\n========== %s ==========\n' "$1"; }
gate()   { # name | command... — run, show the tail, record PASS/FAIL on exit code
  local name="$1"; shift; hdr "$name"
  local out rc; out="$("$@" 2>&1)"; rc=$?; printf '%s\n' "$out" | tail -5
  local last; last="$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -1)"
  if [ "$rc" -eq 0 ]; then record "$name" PASS "${last:-exit 0, no output}"
  else record "$name" FAIL "exit $rc"; fi
}

# ---- Python mode -------------------------------------------------------------
if [ -n "${HK_PY_MODE:-}" ]; then
  PY_MODE="$HK_PY_MODE"; PY_REASON="HK_PY_MODE override"
elif docker info >/dev/null 2>&1; then
  PY_MODE=docker; PY_REASON="docker daemon answers"
else
  PY_MODE=host; PY_REASON="no docker daemon"
fi
record py_mode INFO "$PY_MODE ($PY_REASON)"

# ---- Phase 2 — static checks -------------------------------------------------
gate py_lint  uvx ruff check --isolated --select F src firebase scripts tests
if [ -d "$FE/node_modules" ]; then
  gate fe_types bash -c "cd $FE && npx tsc --noEmit"
  gate fe_lint  bash -c "cd $FE && npm run -s lint"
else
  record fe_types FAIL "$FE/node_modules missing — run npm ci in $FE"
  record fe_lint  FAIL "$FE/node_modules missing — run npm ci in $FE"
fi

# ---- Phase 4 — lock + backend image (the tests below run inside it) ---------
gate uv_lock uv lock --check

if [ "$PY_MODE" = docker ]; then
  gate backend_image docker build -q -f firebase/backend/Dockerfile -t "$IMAGE" .
else
  hdr backend_image; echo "  skipped: host mode"
  record backend_image SKIP "host mode — Cloud Run image not built"
fi

# ---- Phase 3 — tests ---------------------------------------------------------
hdr "tests (pytest tests/, $PY_MODE)"
if [ "$PY_MODE" = docker ]; then
  out="$(docker run --rm -v "$PWD":/repo -w /repo "$IMAGE" bash -c \
    'uv pip install -q --python /app/.venv/bin/python pytest && python -m pytest tests/ -q -p no:cacheprovider' 2>&1)"; rc=$?
else
  out="$(.venv/bin/python -m pytest tests/ -q -p no:cacheprovider 2>&1)"; rc=$?
fi
printf '%s\n' "$out" | tail -8
counts="$(printf '%s\n' "$out" | grep -E '[0-9]+ (passed|failed)' | tail -1)"
p=$(printf '%s' "$counts" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+'); p=${p:-0}
f=$(printf '%s' "$counts" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+'); f=${f:-0}
s=$(printf '%s' "$counts" | grep -oE '[0-9]+ skipped' | grep -oE '[0-9]+'); s=${s:-0}
if [ "$rc" -eq 0 ] && [ "$p" -gt 0 ]; then record tests PASS "passed=$p failed=$f skipped=$s"
else record tests FAIL "exit $rc passed=$p failed=$f skipped=$s"; fi

if [ "$PY_MODE" = docker ]; then docker rmi -f "$IMAGE" >/dev/null 2>&1; fi

# ---- Phase 4 — frontend build, tracked-file hygiene, audit -------------------
if [ -d "$FE/node_modules" ]; then
  gate fe_build bash -c "cd $FE && npm run -s build"
else
  record fe_build FAIL "$FE/node_modules missing — run npm ci in $FE"
fi

hdr "tracked files (secrets / generated artifacts)"
FORBIDDEN=(':(glob)**/.env' ':(glob)**/.env.local' ':(glob)**/*-sa-key.json'
           ':(glob)**/secrets.toml' 'data/' "$FE/.next/" "$FE/node_modules/"
           ':(glob)**/*.log' ':(glob)**/*.tsbuildinfo' ':(glob)**/__pycache__/**')
hits="$( { git ls-files -- "${FORBIDDEN[@]}"; git status --porcelain --untracked-files=all -- "${FORBIDDEN[@]}" | cut -c4-; } | sort -u)"
if [ -z "$hits" ]; then echo "  none"; record tracked_files PASS "no secrets or generated files tracked or staged"
else echo "$hits"; record tracked_files FAIL "$(printf '%s\n' "$hits" | grep -c .) forbidden path(s)"; fi

hdr "npm audit (production deps)"
out="$(cd "$FE" && npm audit --omit=dev 2>&1)"; printf '%s\n' "$out" | tail -3
record npm_audit INFO "$(printf '%s\n' "$out" | grep -E 'vulnerabilit' | tail -1)"

# ---- Phase 5 — log integrity -------------------------------------------------
hdr "housekeeping_log.jsonl integrity"
if [ ! -f housekeeping_log.jsonl ]; then
  record log_integrity FAIL "housekeeping_log.jsonl missing"
elif out="$(python3 -c '
import json
n = 0
for l in open("housekeeping_log.jsonl"):
    if l.strip():
        r = json.loads(l); n += 1
        assert {"schema_version","entry_id","date","trigger","metrics","body_markdown"} <= set(r), r.get("entry_id")
print(n, "records")' 2>&1)"; then
  echo "  $out"; record log_integrity PASS "$out parse, schema ok"
else
  echo "$out"; record log_integrity FAIL "a line does not parse or lacks a field"
fi

hdr "SUMMARY"; printf '%s' "$SUMMARY"
[ "$GATE_FAIL" -eq 0 ] && { echo "OVERALL: PASS"; exit 0; } || { echo "OVERALL: FAIL"; exit 1; }
