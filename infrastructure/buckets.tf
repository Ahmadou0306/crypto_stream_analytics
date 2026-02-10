# Creation du bucket pour archivage
resource "google_storage_bucket" "archived_bucket_function" {
  name          = "${var.project_name}-archived_function"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "function-archive"
  }
}



# Output
output "bucket_archived_bucket_function_name" {
  description = "Nom du bucket d'ingestion des données "
  value       = google_storage_bucket.archived_bucket_function.name
}

# Creation du bucket
resource "google_storage_bucket" "crypto_stream_bucket" {
  name          = "${var.project_name}-data-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  versioning {
    enabled = var.environment == "prod"
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}


# Output
output "bucket_crypto_stream_bucket_name" {
  description = "Nom du bucket d'ingestion des données "
  value       = google_storage_bucket.crypto_stream_bucket.name
}


# Creation du bucket pour logs
resource "google_storage_bucket" "logs_bucket" {
  name          = "${var.project_name}-logs-${var.environment}"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  # Lifecycle pour gérer la rétention des logs
  lifecycle_rule {
    condition {
      age = 30 # Garder 30 jours
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90 # Supprimer après 90 jours
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "logs"
  }
}



# Output
output "logs_bucket_name" {
  description = "Nom du bucket de logs"
  value       = google_storage_bucket.logs_bucket.name
}