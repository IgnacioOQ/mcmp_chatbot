#!/usr/bin/env bash
# Deploy the MCMP scraper to a Cloud Run Job and schedule it with Cloud Scheduler.
set -euo pipefail

PROD_BRANCH="firebase-branch"
PROJECT_ID="mcmp-firebase"
REGION="us-central1"
AR_REPO="mcmp-firebase-app"
IMAGE="scraper"
JOB="mcmp-firebase-scraper"
SCHEDULE="0 3 * * 1,4"  # Mondays and Thursdays at 3 AM
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
  --config firebase/scraper/cloudbuild.yaml \
  --substitutions=_TAG="${SHORT_SHA}" \
  --project="${PROJECT_ID}" \
  .

# --- deploy to Cloud Run Job ------------------------------------------------
echo ">> Deploying ${JOB} to Cloud Run Jobs..."
gcloud run jobs deploy "${JOB}" \
  --image="${IMAGE_URI}:${SHORT_SHA}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${RUNTIME_SA}" \
  --max-retries=0 \
  --task-timeout=30m

# --- configure Cloud Scheduler ----------------------------------------------
echo ">> Configuring Cloud Scheduler job..."
if gcloud scheduler jobs describe "${JOB}-schedule" --location="${REGION}" --project="${PROJECT_ID}" > /dev/null 2>&1; then
    echo "Updating existing scheduler job..."
    gcloud scheduler jobs update http "${JOB}-schedule" \
        --location="${REGION}" \
        --project="${PROJECT_ID}" \
        --schedule="${SCHEDULE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run" \
        --http-method=POST \
        --oauth-service-account-email="${RUNTIME_SA}"
else
    echo "Creating new scheduler job..."
    gcloud scheduler jobs create http "${JOB}-schedule" \
        --location="${REGION}" \
        --project="${PROJECT_ID}" \
        --schedule="${SCHEDULE}" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run" \
        --http-method=POST \
        --oauth-service-account-email="${RUNTIME_SA}"
fi

echo ">> Done. Scraper job deployed and scheduled for ${SCHEDULE}."
