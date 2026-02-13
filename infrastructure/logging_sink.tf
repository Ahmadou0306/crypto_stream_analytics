# ========================================
# LOG SINK : CLOUD LOGGING → GCS
# ========================================

# Sink pour les logs Dataflow
resource "google_logging_project_sink" "dataflow_logs_sink" {
  name        = "dataflow-logs-to-gcs"
  description = "Export automatique des logs Dataflow vers GCS pour archivage"

  # Destination : bucket GCS avec structure personnalisée
  destination = "storage.googleapis.com/${google_storage_bucket.logs_bucket.name}/dataflow"

  # seulement Dataflow
  filter = <<-EOT
    resource.type="dataflow_step"
    AND severity >= INFO
  EOT

  # Créer une identité unique (Service Account) pour ce sink
  unique_writer_identity = true
}

# Sink pour les logs Cloud Run - ingestion WebSocket
resource "google_logging_project_sink" "cloud_run_logs_sink" {
  name        = "cloud-run-logs-to-gcs"
  description = "Export automatique des logs Cloud Run vers GCS pour archivage"

  # Destination avec sous-dossier "cloud_run"
  destination = "storage.googleapis.com/${google_storage_bucket.logs_bucket.name}/cloud_run"

  # Filtrer les logs Cloud Run
  filter = <<-EOT
    resource.type="cloud_run_revision"
    AND resource.labels.service_name="crypto-stream-ingestion"
    AND severity >= INFO
  EOT

  unique_writer_identity = true
}

# Sink pour tous les autres logs
resource "google_logging_project_sink" "all_logs_sink" {
  name        = "all-logs-to-gcs"
  description = "Export de tous les logs du projet vers GCS"

  # Destination avec sous-dossier "all_logs"
  destination = "storage.googleapis.com/${google_storage_bucket.logs_bucket.name}/streaming"

  # Pas de filtre = tous les logs
  filter = "severity >= WARNING" # Seulement WARNING et ERROR

  unique_writer_identity = true
}



output "dataflow_sink_name" {
  value       = google_logging_project_sink.dataflow_logs_sink.name
  description = "Nom du sink Dataflow"
}

output "cloud_run_sink_name" {
  value       = google_logging_project_sink.cloud_run_logs_sink.name
  description = "Nom du sink Cloud Run"
}
output "other_sink_name" {
  value       = google_logging_project_sink.all_logs_sink.name
  description = "Nom des autres sink"
}