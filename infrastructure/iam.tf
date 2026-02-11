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

# Role de creation d'objet dans le bucket
resource "google_storage_bucket_iam_member" "stream_logs_writer" {
  bucket = google_storage_bucket.logs_bucket.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}

# Role de creation de lecture dans le bucket
resource "google_storage_bucket_iam_member" "stream_logs_reader" {
  bucket = google_storage_bucket.logs_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}

#permission d'ecrire dans cloud logging
resource "google_project_iam_member" "stream_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.crypto_stream_ingestion_sa.email}"
}
#==========================================================================
# Service Account dédié à Big Query
#==========================================================================

# Service Account BigQuery créé automatiquement par Google donc pas besoin de le mettre

# Data source pour récupérer le project number
data "google_project" "current" {
  project_id = var.project_id
}

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


