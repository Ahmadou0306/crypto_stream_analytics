# Creation du bucket pour archivage
resource "google_storage_bucket" "archived_bucket_function" {
  name          = "${var.project_name}-archived_function"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  #lifecycle {
  #  prevent_destroy = true
  #}

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
  name     = "${var.project_name}-logs-${var.environment}"
  location = var.region
  # Empêcher la suppression accidentelle
  force_destroy = false

  # Versioning pour garder l'historique des modifications
  versioning {
    enabled = true
  }

  # Politique de cycle de vie pour optimiser les coûts
  lifecycle_rule {
    condition {
      age = 90 # Logs de plus de 90 jours
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE" # Encore moins cher (0.004$/GB/mois)
    }
  }

  lifecycle_rule {
    condition {
      age = 365 # Logs de plus de 1 an
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE" # Le moins cher (0.0012$/GB/mois)
    }
  }

  lifecycle_rule {
    condition {
      age = 2555 # Logs de plus de 7 ans (compliance légale)
    }
    action {
      type = "Delete" # Supprimer définitivement
    }
  }

  labels = {
    environment = var.environment
    purpose     = "logs-archive"
    managed_by  = "terraform"
  }
}



# Output
output "logs_bucket_name" {
  description = "Nom du bucket de logs"
  value       = google_storage_bucket.logs_bucket.name
}



# ========================================
# BUCKET DATAFLOW (staging/temp)
# ========================================

resource "google_storage_bucket" "dataflow_bucket" {
  name          = "${var.project_id}-dataflow"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7 # Nettoyer les fichiers temporaires après 7 jours
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "dataflow-temp"
  }
}

# Dossiers dans le bucket
resource "google_storage_bucket_object" "dataflow_staging" {
  name    = "staging/"
  content = " "
  bucket  = google_storage_bucket.dataflow_bucket.name
}

resource "google_storage_bucket_object" "dataflow_temp" {
  name    = "temp/"
  content = " "
  bucket  = google_storage_bucket.dataflow_bucket.name
}
output "dataflow_bucket_bucket_name" {
  description = "Nom du bucket dataflow des données "
  value       = google_storage_bucket.dataflow_bucket.name
}