#!/usr/bin/env bash
# Deploy the MCMP Firebase chat backend to Cloud Run (IAM-only).
# Hard branch guard: refuses to run on any branch except firebase-branch.
# Pattern adapted from the Chatbot Template deploy-backend.sh.
set -euo pipefail

PROD_BRANCH="firebase-branch"
PROJECT_ID="mcmp-firebase"
REGION="us-central1"
AR_REPO="mcmp-firebase-app"
IMAGE="backend"
SERVICE="mcmp-firebase-backend"
RUNTIME_SA="mcmp-firebase-app-sa@mcmp-firebase.iam.gserviceaccount.com"

# --- branch guard -----------------------------------------------------------
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "$PROD_BRANCH" ]]; then
  echo "ERROR: deploys must run on '$PROD_BRANCH' (currently on '$CURRENT_BRANCH')." >&2
  exit 1
fi

# --- build from repo root ---------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "WARNING: working tree has uncommitted changes; building current HEAD source." >&2
fi

SHORT_SHA="$(git rev-parse --short HEAD)"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE}"

echo ">> Building ${IMAGE_URI}:${SHORT_SHA} via Cloud Build..."
gcloud builds submit \
  --config firebase/backend/cloudbuild.yaml \
  --substitutions=_TAG="${SHORT_SHA}" \
  --project="${PROJECT_ID}" \
  .

# --- deploy to Cloud Run ----------------------------------------------------
echo ">> Deploying ${SERVICE} to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image="${IMAGE_URI}:${SHORT_SHA}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --no-allow-unauthenticated \
  --service-account="${RUNTIME_SA}" \
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest,SHEETS_SA_JSON=SHEETS_SA_JSON:latest,SHEETS_ID=SHEETS_ID:latest \
  --set-env-vars=DATA_BACKEND=firestore \
  --min-instances=1 --max-instances=2 --memory=512Mi --cpu=1

# --- smoke test -------------------------------------------------------------
URL="$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"
echo ">> Smoke test ${URL}/health ..."
TOKEN="$(gcloud auth print-identity-token)"
curl -fsS -H "Authorization: Bearer ${TOKEN}" "${URL}/health" && echo
echo ">> Done. Backend URL: ${URL}"
