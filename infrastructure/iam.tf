# Data source pour récupérer le project number
data "google_project" "current" {
  project_id = var.project_id
}

#==========================================================================
# Service Account dédié à la fonction fetch_historical de cloud run
#==========================================================================
resource "google_service_account" "function_sa" {
  account_id   = "fetch-historical-sa"
  display_name = "Service Account pour fetch_historical"
}

# Permission d'écrire dans le buckets de données
resource "google_storage_bucket_iam_member" "function_crypto_stream_bucket_access" {
  bucket = google_storage_bucket.crypto_stream_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

# Permission de lire le cocde archivé sur le bucket d'archivage
resource "google_storage_bucket_iam_member" "function_archived_bucket_access" {
  bucket = google_storage_bucket.archived_bucket_function.name
  role   = "roles/storage.objectViewer" # Lecture seule suffisante
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

# Permission d'écrire dans le bucket des logs
resource "google_storage_bucket_iam_member" "function_logs_bucket_access" {
  bucket = google_storage_bucket.logs_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

#=================================================
# CLoud run Service - ingestion Streaming
#=================================================
#Service account
resource "google_service_account" "crypto_stream_ingestion_sa" {
  account_id   = "crypto-stream-ingestion-sa"
  display_name = "Service Account for Crypto Stream Ingestion"
  project      = var.project_id
}

# Role Admin sur le bucket logs
resource "google_storage_bucket_iam_member" "stream_logs_reader" {
  bucket = google_storage_bucket.logs_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}

#permission d'ecrire dans cloud logging
resource "google_project_iam_member" "stream_log_access" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}

# Permet au service account d'ingestion streaming de publier dans pub/sub
resource "google_pubsub_topic_iam_member" "crypto_stream_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.crypto_klines_raw.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}

#==========================================================================
# Service Account dédié à Big Query
#==========================================================================

# Service Account BigQuery créé automatiquement par Google donc pas besoin de le mettre



# Permission BigQuery de lecture sur le bucket
# Permission BigQuery de lecture sur le bucket
resource "google_storage_bucket_iam_member" "bigquery_reader" {
  bucket = google_storage_bucket.crypto_stream_bucket.name
  role   = "roles/storage.objectViewer"

  # Format correct du SA BigQuery
  member = "serviceAccount:bq-${data.google_project.current.number}@bigquery-encryption.iam.gserviceaccount.com"

  # S'assurer que les tables existent avant de donner les permissions
  depends_on = [
    google_bigquery_table.historical_raw
  ]
}


#============================================================================
#PERMISSIONS PUB/SUB
#============================================================================

# Permissions pour la subscription DLQ de publier sur le topic DLQ
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.crypto_klines_dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Permissions pour la subscription principale de subscribe
resource "google_pubsub_subscription_iam_member" "dataflow_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.crypto_klines_dataflow.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}


#============================================================================
#PERMISSIONS DATAFLOW
#============================================================================

# ============================================================================
# SERVICE ACCOUNT DATAFLOW
# ============================================================================

# Service account
resource "google_service_account" "dataflow_stream_sa" {
  account_id   = "dataflow-stream-sa"
  display_name = "Service Account pour Dataflow Streaming"
  project      = var.project_id
}


# Permission Dataflow Worker
resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow_stream_sa.email}"
}

# Permission BigQuery Data Editor
resource "google_project_iam_member" "dataflow_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow_stream_sa.email}"
}

# Permission Pub/Sub Subscriber
resource "google_project_iam_member" "dataflow_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.dataflow_stream_sa.email}"
}


# Permission Storage sur bucket de données
resource "google_storage_bucket_iam_member" "dataflow_storage_data" {
  bucket = google_storage_bucket.crypto_stream_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow_stream_sa.email}"
}

# Permission Storage sur bucket de logs
resource "google_storage_bucket_iam_member" "dataflow_storage_logs" {
  bucket = google_storage_bucket.logs_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow_stream_sa.email}"
}