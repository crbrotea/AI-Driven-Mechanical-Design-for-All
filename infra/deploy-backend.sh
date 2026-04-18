#!/usr/bin/env bash
# Deploy the Interpreter backend to Cloud Run.
# Usage: ./infra/deploy-backend.sh [cors_origins]
#
# Required environment: GCP_PROJECT_ID, GCP_REGION
set -euo pipefail

: "${GCP_PROJECT_ID:?must be set}"
: "${GCP_REGION:?must be set}"

CORS="${1:-https://mechdesign-ai.vercel.app}"

cd "$(dirname "$0")/../apps/backend"

gcloud run deploy orchestrator \
  --source . \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 60 \
  --set-env-vars "GCP_PROJECT_ID=$GCP_PROJECT_ID,GCP_REGION=$GCP_REGION,VERTEX_AI_ENDPOINT=gemma-4-instruct,CORS_ALLOWED_ORIGINS=$CORS,GCS_BUCKET_ARTIFACTS=mechdesign-artifacts"

echo "Deployed. Health check:"
SERVICE_URL=$(gcloud run services describe orchestrator \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" --format="value(status.url)")
curl -fsSL "$SERVICE_URL/healthz" && echo
