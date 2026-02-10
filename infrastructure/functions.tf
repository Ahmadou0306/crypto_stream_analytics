# Service Account dédié à la fonction
resource "google_service_account" "function_sa" {
  account_id   = "fetch-historical-sa"
  display_name = "Service Account pour fetch_historical"
}

# Permission d'écrire dans les buckets de données
resource "google_storage_bucket_iam_member" "function_bucket_access" {
  bucket = google_storage_bucket.crypto_stream_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

# Archiver le code source
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "../cloud_functions/fetch_historical"
  output_path = "${path.module}/tmp/fetch_historical.zip"
}

# Upload le code dans le bucket
resource "google_storage_bucket_object" "function_archive" {
  name   = "fetch_historical-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.archived_function.name
  source = data.archive_file.function_source.output_path
}

# Cloud Function 2nd gen (Cloud Run-based)
resource "google_cloudfunctions2_function" "fetch_historical" {
  name        = "fetch-historical"
  location    = var.region
  description = "Récupération données historiques BTC et ETH"

  build_config {
    runtime     = "python311"
    entry_point = "fetch_historical_data"
    
    source {
      storage_source {
        bucket = google_storage_bucket.archived_function.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    min_instance_count    = 0
    available_memory      = "1Gi"
    timeout_seconds       = 540
    
    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
    
    service_account_email = google_service_account.function_sa.email
    
    environment_variables = {
      BUCKET_NAME = google_storage_bucket.crypto_stream_bucket.name
    }
  }
}

# Output de l'URL
output "function_url" {
  value       = google_cloudfunctions2_function.fetch_historical.service_config[0].uri
  description = "URL de la fonction Cloud Run (authentification requise)"
}