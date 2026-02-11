# Ajouter dans un nouveau fichier artifact_registry.tf

resource "google_artifact_registry_repository" "crypto_stream_rg" {
  location      = var.region
  repository_id = "crypto-stream"
  description   = "Docker images pour streaming crypto"
  format        = "DOCKER"
  
  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

output "artifact_registry_url" {
  description = "URL du repository Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.crypto_stream_rg.repository_id}"
}