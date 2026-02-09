# 1. Service Account
resource "google_service_account" "crypto_sa" {
  account_id   = "${var.project_name}-sa-${var.environment}"
  display_name = "Crypto Analytics SA (${var.environment})"
}

# 2. Permission Storage 
resource "google_project_iam_member" "sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.crypto_sa.email}"
}

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