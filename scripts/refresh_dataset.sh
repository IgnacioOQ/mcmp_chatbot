#!/usr/bin/env bash
#
# refresh_dataset.sh — scheduled dataset refresh for the MCMP chatbot.
#
# This is the single entry point the scheduled (Claude Code on the web) job
# should call. It GUARANTEES the scrape happens on the branch where data/ is
# tracked (routines), so the resulting changes can actually be committed and
# pushed. Running the scraper on any branch where data/ is gitignored silently
# produces no committable changes.
#
# After committing+pushing the refreshed data/ files it pushes the same data to
# Firestore (the live Firebase app reads from Firestore, not from data/*.json),
# so the deployed chatbot is updated in the same run.
#
# It is idempotent and safe to re-run: it only commits/pushes when data/
# actually changed.
set -euo pipefail

BRANCH="routines"
FIREBASE_PROJECT="${MCMP_FIREBASE_PROJECT:-mcmp-firebase}"

cd "$(git rev-parse --show-toplevel)"

echo "[refresh] Ensuring we are on $BRANCH (where data/ is tracked)..."
git fetch origin "$BRANCH"
git switch "$BRANCH"
# Build on the latest published dataset; fast-forward only so we never
# silently discard or rewrite published history.
git pull --ff-only origin "$BRANCH"

echo "[refresh] Running scraper..."
python scripts/update_dataset.py "$@"

if [ -z "$(git status --porcelain data/)" ]; then
  echo "[refresh] No dataset changes; nothing to commit or migrate."
  exit 0
fi

echo "[refresh] Committing dataset changes..."
git add data/
git commit -m "chore: refresh dataset $(date -u +%Y-%m-%d)"

echo "[refresh] Pushing to $BRANCH..."
# Retry on transient network failures with exponential backoff.
pushed=false
for attempt in 1 2 3 4; do
  if git push origin "HEAD:$BRANCH"; then
    echo "[refresh] Pushed dataset update to $BRANCH."
    pushed=true
    break
  fi
  wait=$((2 ** attempt))
  echo "[refresh] Push failed (attempt $attempt). Retrying in ${wait}s..."
  sleep "$wait"
done

if [ "$pushed" != true ]; then
  echo "[refresh] Push failed after 4 attempts." >&2
  exit 1
fi

# Push the refreshed data to Firestore so the live Firebase app is updated.
# Requires Firebase credentials. In a Google Cloud runtime the attached service
# account supplies these automatically; in other environments (e.g. the Claude
# Code on the web cloud runner) there is no attached SA, so provide a key:
#   - set GCP_SA_KEY to the full JSON contents of a service-account key (for
#     mcmp-firebase-app-sa@mcmp-firebase, which has roles/datastore.user), OR
#   - set GOOGLE_APPLICATION_CREDENTIALS to a key file path / use ADC directly.
# The migration is an idempotent upsert that never deletes (accumulation model).
if [ -n "${GCP_SA_KEY:-}" ] && [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  printf '%s' "$GCP_SA_KEY" > /tmp/gcp-sa-key.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-sa-key.json
  echo "[refresh] Wrote service-account key from GCP_SA_KEY to \$GOOGLE_APPLICATION_CREDENTIALS."
fi

echo "[refresh] Migrating dataset to Firestore (project: $FIREBASE_PROJECT)..."
if python firebase/scripts/migrate_to_firestore.py --project="$FIREBASE_PROJECT"; then
  echo "[refresh] Firestore updated; live app is now current."
else
  echo "[refresh] WARNING: Firestore migration failed — data/ was committed to" >&2
  echo "[refresh] $BRANCH but the live app was NOT updated. Check Firebase" >&2
  echo "[refresh] credentials, then re-run: python firebase/scripts/migrate_to_firestore.py --project=$FIREBASE_PROJECT" >&2
  exit 1
fi

echo "[refresh] Done."
