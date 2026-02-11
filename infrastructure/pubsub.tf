resource "google_pubsub_topic" "crypto_klines_raw" {
  name    = "crypto-klines-raw"
  project = var.project_id

  # Retention des messages non consommés : 7 jours
  message_retention_duration = "604800s"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "streaming-ingestion"
  }
}

resource "google_pubsub_topic" "crypto_klines_dlq" {
  name    = "crypto-klines-dlq"
  project = var.project_id

  message_retention_duration = "604800s"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "dead-letter-queue"
  }
}

# Subscription DLQ (pour inspecter les messages en erreur)
resource "google_pubsub_subscription" "crypto_klines_dlq_sub" {
  name    = "crypto-klines-dlq-sub"
  project = var.project_id
  topic   = google_pubsub_topic.crypto_klines_dlq.name

  ack_deadline_seconds = 60

  # Ne jamais expirer
  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
    purpose     = "dead-letter-inspection"
    managed_by  = "terraform"
  }
}


resource "google_pubsub_subscription" "crypto_klines_dataflow" {
  name    = "crypto-klines-dataflow-sub"
  project = var.project_id
  topic   = google_pubsub_topic.crypto_klines_raw.name

  # Acknowledge deadline : 60 secondes
  ack_deadline_seconds = 60

  # Message retention : 7 jours
  message_retention_duration = "604800s"

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.crypto_klines_dlq.id
    max_delivery_attempts = 5
  }

  # Ne jamais expirer
  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
    consumer    = "dataflow"
    managed_by  = "terraform"
  }

  depends_on = [
    google_pubsub_topic.crypto_klines_raw,
    google_pubsub_topic.crypto_klines_dlq
  ]
}

resource "google_pubsub_subscription" "crypto_klines_monitoring" {
  name    = "crypto-klines-monitoring-sub"
  project = var.project_id
  topic   = google_pubsub_topic.crypto_klines_raw.name

  ack_deadline_seconds = 30

  # Cette subscription expire si non utilisée pendant 31 jours
  expiration_policy {
    ttl = "2678400s" # 31 jours
  }

  labels = {
    environment = var.environment
    purpose     = "manual-monitoring"
    managed_by  = "terraform"
  }
}



output "pubsub_topic_klines_raw" {
  description = "Nom du topic Pub/Sub pour klines raw"
  value       = google_pubsub_topic.crypto_klines_raw.name
}

output "pubsub_topic_klines_dlq" {
  description = "Nom du topic Pub/Sub DLQ"
  value       = google_pubsub_topic.crypto_klines_dlq.name
}

output "pubsub_subscription_dataflow" {
  description = "Nom de la subscription Dataflow"
  value       = google_pubsub_subscription.crypto_klines_dataflow.name
}

output "pubsub_subscription_monitoring" {
  description = "Nom de la subscription monitoring"
  value       = google_pubsub_subscription.crypto_klines_monitoring.name
}

output "pubsub_subscription_dlq" {
  description = "Nom de la subscription DLQ"
  value       = google_pubsub_subscription.crypto_klines_dlq_sub.name
}