output "bucket_name" {
  description = "Nom du bucket créé"
  value       = google_storage_bucket.crypto_stream_bucket.name
}