#!/usr/bin/env bash
set -euo pipefail

PROJECT="${PROJECT:-mechdesign-ai}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-mechdesign-backend}"
BUCKET="${BUCKET:-mechdesign-ai-artifacts}"
SA_NAME="${SA_NAME:-mechdesign-runtime}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
REPO="${REPO:-backend}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"

echo "==> Project: ${PROJECT}, Region: ${REGION}, Service: ${SERVICE}"

# 1. Enable required APIs (idempotent)
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  --project="${PROJECT}"

# 2. Create Artifact Registry repo (idempotent)
gcloud artifacts repositories describe "${REPO}" \
  --project="${PROJECT}" --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${REPO}" \
       --project="${PROJECT}" --location="${REGION}" --repository-format=docker

# 3. Create runtime SA + grant roles (idempotent)
gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT}" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "${SA_NAME}" \
       --project="${PROJECT}" --display-name="Cloud Run runtime for ${SERVICE}"

for role in \
    roles/storage.objectAdmin \
    roles/aiplatform.user \
    roles/datastore.user \
    roles/serviceusage.serviceUsageConsumer
do
  for attempt in 1 2 3; do
    if gcloud projects add-iam-policy-binding "${PROJECT}" \
         --member="serviceAccount:${SA_EMAIL}" \
         --role="${role}" --condition=None >/dev/null 2>&1; then
      break
    fi
    echo "   (retry ${attempt} for ${role})"
    sleep 2
  done
done

for attempt in 1 2 3; do
  if gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
       --member="serviceAccount:${SA_EMAIL}" \
       --role="roles/iam.serviceAccountTokenCreator" \
       --project="${PROJECT}" >/dev/null 2>&1; then
    break
  fi
  echo "   (retry ${attempt} for token creator)"
  sleep 2
done

# 4. Build image via Cloud Build (no local Docker required)
#    Dockerfile uses relative COPY paths, so the build context is apps/backend.
gcloud builds submit \
  --project="${PROJECT}" \
  --tag="${IMAGE}" \
  apps/backend

# 5. Deploy
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${SA_EMAIL}" \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=120 \
  --concurrency=20 \
  --max-instances=5 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCP_REGION=${REGION},VERTEX_AI_ENDPOINT=gemini-2.5-flash,GEMMA_TEMPERATURE=0.2,GEMMA_MAX_TOKENS=2048,GEMMA_TIMEOUT_SECONDS=60,GCS_BUCKET_ARTIFACTS=${BUCKET},SIGNED_URL_TTL_HOURS=24,SESSION_TTL_HOURS=24,SESSION_MAX_RETRIES=5,RATE_LIMIT_PER_MINUTE=30,DEGRADED_MODE_FAILURE_THRESHOLD=2,DEGRADED_MODE_DURATION_SECONDS=60,CORS_ALLOWED_ORIGINS=http://localhost:3000"

URL=$(gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" --region="${REGION}" --format='value(status.url)')

echo "==> Deployed: ${URL}"
echo "==> Set NEXT_PUBLIC_API_URL=${URL} in Vercel (Production scope)"
