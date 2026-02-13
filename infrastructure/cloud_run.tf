

# Archiver le code source
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = "${path.root}/../cloud_run/fetch_historical"
  output_path = "${path.root}/.terraform/tmp/fetch_historical.zip"
}

# Upload le code dans le bucket
resource "google_storage_bucket_object" "function_archive" {
  name   = "fetch_historical-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.archived_bucket_function.name
  source = data.archive_file.function_source.output_path
}

# Cloud Function 2nd gen (Cloud Run-based)
resource "google_cloudfunctions2_function" "fetch_historical" {
  depends_on = [
    google_storage_bucket_object.function_archive,
    google_service_account.function_sa
  ]
  name        = "fetch-historical"
  location    = var.region
  description = "Récupération données historiques BTC et ETH"

  build_config {
    runtime     = "python311"
    entry_point = "fetch_historical_data"

    source {
      storage_source {
        bucket = google_storage_bucket.archived_bucket_function.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    min_instance_count = 0
    available_memory   = "1Gi"
    timeout_seconds    = 3600

    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true

    service_account_email = google_service_account.function_sa.email

    environment_variables = {
      BUCKET_NAME = google_storage_bucket.crypto_stream_bucket.name
    }
  }
}


# Autoriser invocations authentifiées
resource "google_cloud_run_service_iam_member" "invoker" {
  location = google_cloudfunctions2_function.fetch_historical.location
  service  = google_cloudfunctions2_function.fetch_historical.name
  role     = "roles/run.invoker"
  member   = "user:${var.email_props}"
}

# Output de l'URL
output "function_url" {
  value       = google_cloudfunctions2_function.fetch_historical.service_config[0].uri
  description = "URL de la fonction Cloud Run (authentification requise)"
}



#=================================================
# CLoud run Service - ingestion Streaming
#=================================================

resource "google_cloud_run_v2_service" "crypto_stream_ingestion_run" {
  name     = "crypto-stream-ingestion"
  location = var.region
  project  = var.project_id

  template {
    containers {
      # Image Docker
      image = "europe-west1-docker.pkg.dev/${var.project_id}/crypto-stream/crypto-stream-ingestion:latest"

      # Port exposé
      ports {
        container_port = 8080
      }

      # Variables d'environnement
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCS_BUCKET_LOGS"
        value = "${var.project_name}-logs-${var.environment}"
      }

      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.crypto_klines_raw.name
      }

      env {
        name  = "BINANCE_STREAM_TYPE"
        value = "kline_5m"
      }

      # Ressources
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = false
      }

      # vérifier que le service démarre correctement
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      # Liveness probe : vérifie que le service est toujours vivant
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 30
        timeout_seconds       = 3
        period_seconds        = 60 # Verifie toutes les 60 secondes
        failure_threshold     = 3  # Redémarre après 3 échecs consécutifs
      }
    }

    # SCALING
    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

    # Timeout maximum : 1 heure
    timeout = "3600s"

    # Service Account
    service_account = google_service_account.crypto_stream_ingestion_sa.email

    # Labels sur les instances
    labels = {
      app = "crypto-stream"
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "websocket-ingestion"
  }

  depends_on = [
    google_service_account.crypto_stream_ingestion_sa,
    google_pubsub_topic.crypto_klines_raw
  ]

  # Ignorer les changements sur l'image (sera déployée séparément)
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}


resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.crypto_stream_ingestion_run.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}


output "cloud_run_stream_url" {
  description = "URL du service Cloud Run streaming"
  value       = google_cloud_run_v2_service.crypto_stream_ingestion_run.uri
}
