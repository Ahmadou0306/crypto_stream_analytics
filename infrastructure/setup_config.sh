#!/bin/bash

# Configuration
PROJECT_ID="training-gcp-484513"
SA_NAME="terraform-admin-crypto-stream-analytics"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="./configs/credential.json"

echo "Project ID: ${PROJECT_ID}"

# Définition le projet par défaut
gcloud config set project ${PROJECT_ID}

# Activation toutes les APIs nécessaires
echo ""
echo "Activation des APIs GCP..."
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  storage.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  pubsub.googleapis.com \
  dataflow.googleapis.com \
  bigquery.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project=${PROJECT_ID}

echo "APIs activées"

# Création le Service Account Terraform
echo ""
echo "Création du Service Account Terraform..."
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="Terraform Admin Service Account" \
  --description="Service Account pour gérer l'infrastructure via Terraform" \
  --project=${PROJECT_ID}

echo "Service Account créé: ${SA_EMAIL}"

# Attribution les rôles nécessaires au niveau projet
echo "Attribution des rôles IAM..."

ROLES=(
  "roles/editor"
  "roles/iam.serviceAccountAdmin"
  "roles/iam.serviceAccountUser"
  "roles/storage.admin"
  "roles/cloudfunctions.admin"
  "roles/cloudbuild.builds.editor"
  "roles/run.admin"
  "roles/pubsub.admin"
  "roles/dataflow.admin"
  "roles/bigquery.admin"
  "roles/logging.admin"
  "roles/monitoring.admin"
)

for ROLE in "${ROLES[@]}"; do
  echo "Ajout du rôle: ${ROLE}"
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

echo "Tous les Rôles attribués"

# Permissions spéciales sur Compute Engine SA

echo "Configuration des permissions Compute Engine..."
COMPUTE_SA="${PROJECT_ID//[^0-9]/}-compute@developer.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding ${COMPUTE_SA} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet

echo "Permissions Compute Engine configurées"

# 6. Créer une clé JSON
echo "Génération de la clé JSON..."
gcloud iam service-accounts keys create ${KEY_FILE} \
  --iam-account=${SA_EMAIL} \
  --project=${PROJECT_ID}

echo "Clé générée: ${KEY_FILE}"