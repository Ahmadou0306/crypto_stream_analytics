# Dataset BigQuery
resource "google_bigquery_dataset" "crypto_raw" {
  dataset_id  = "crypto_raw"
  location    = var.region
  description = "Crypto raw dataset pour la récupération des données brutes en temps réel"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# External table historique pour BTC et ETH 
resource "google_bigquery_table" "historical_raw" {
  dataset_id = google_bigquery_dataset.crypto_raw.dataset_id
  table_id   = "historical_raw"

  deletion_protection = true


  external_data_configuration {
    autodetect    = true
    source_format = "CSV"
    source_uris = [
      "gs://${google_storage_bucket.crypto_stream_bucket.name}/historical/btcusdt/*.csv",
      "gs://${google_storage_bucket.crypto_stream_bucket.name}/historical/ethusdt/*.csv",
      "gs://${google_storage_bucket.crypto_stream_bucket.name}/historical/solusdt/*.csv",

    ]

    csv_options {
      skip_leading_rows = 1
      quote             = "\""
    }
  }

  labels = {
    data_type   = "historical"
    environment = var.environment
  }
}

# Pas la peine de creer streaming_raw dans crypto_raw car dataflow le fera lui meme


# Dataset BigQuery
resource "google_bigquery_dataset" "crypto_analytics" {
  dataset_id  = "crypto_analytics"
  location    = var.region
  description = "Crypto Analytics dataset pour l'analyse en temps réel"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Dimension Dates
resource "google_bigquery_table" "dim_dates" {
  dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id
  table_id   = "dim_dates"

  deletion_protection = false


  schema = jsonencode([
    { name = "date", type = "DATE", mode = "REQUIRED" },
    { name = "year", type = "INT64", mode = "REQUIRED" },
    { name = "month", type = "INT64", mode = "REQUIRED" },
    { name = "month_name", type = "STRING", mode = "REQUIRED" },
    { name = "day", type = "INT64", mode = "REQUIRED" },
    { name = "day_of_week", type = "INT64", mode = "REQUIRED" },
    { name = "day_of_week_name", type = "STRING", mode = "REQUIRED" }
  ])

  clustering = ["year", "month"]
}

# Dimension Heures
resource "google_bigquery_table" "dim_hours" {
  dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id
  table_id   = "dim_hours"

  deletion_protection = false


  schema = jsonencode([
    { name = "hours", type = "INT64", mode = "REQUIRED" },
    { name = "hour_12", type = "INT64", mode = "REQUIRED" },
    { name = "am_pm", type = "STRING", mode = "REQUIRED" },
    { name = "is_worked_hours", type = "BOOL", mode = "REQUIRED" },
    { name = "is_rush_hour", type = "BOOL", mode = "REQUIRED" }
  ])
}

# Dimension Symboles
resource "google_bigquery_table" "dim_symboles" {
  dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id
  table_id   = "dim_symboles"

  deletion_protection = false


  schema = jsonencode([
    { name = "symbol", type = "STRING", mode = "REQUIRED" },
    { name = "symbole_libelle", type = "STRING", mode = "REQUIRED" },
    { name = "devise_cotation", type = "STRING", mode = "REQUIRED" },
    { name = "devise_cotation_nom", type = "STRING", mode = "REQUIRED" }
  ])
}


# Table unifiée (historique + streaming)
resource "google_bigquery_table" "market_data_unified" {
  dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id
  table_id   = "market_data_unified"

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "date"
  }

  clustering = ["symbol", "hour"]

  schema = jsonencode([
    # Dimensions temporelles
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "date", type = "DATE", mode = "REQUIRED" },
    { name = "hour", type = "INT64", mode = "REQUIRED" },
    { name = "day_of_week", type = "STRING", mode = "NULLABLE" },

    # Dimensions crypto
    { name = "symbol", type = "STRING", mode = "REQUIRED" },

    # OHLCV
    { name = "open", type = "FLOAT64", mode = "REQUIRED" },
    { name = "high", type = "FLOAT64", mode = "REQUIRED" },
    { name = "low", type = "FLOAT64", mode = "REQUIRED" },
    { name = "close", type = "FLOAT64", mode = "REQUIRED" },
    { name = "volume", type = "FLOAT64", mode = "REQUIRED" },
    { name = "trades", type = "INT64", mode = "NULLABLE" },

    # Indicateurs techniques
    { name = "sma_20", type = "FLOAT64", mode = "NULLABLE" },
    { name = "ema_50", type = "FLOAT64", mode = "NULLABLE" },
    { name = "rsi_14", type = "FLOAT64", mode = "NULLABLE" },
    { name = "macd", type = "FLOAT64", mode = "NULLABLE" },
    { name = "macd_signal", type = "FLOAT64", mode = "NULLABLE" },
    { name = "bb_upper", type = "FLOAT64", mode = "NULLABLE" },
    { name = "bb_middle", type = "FLOAT64", mode = "NULLABLE" },
    { name = "bb_lower", type = "FLOAT64", mode = "NULLABLE" },

    # Métadonnées
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "ingestion_timestamp", type = "TIMESTAMP", mode = "REQUIRED" }
  ])

  labels = {
    data_type   = "unified"
    environment = var.environment
  }
}

# Outputs
output "bigquery_dataset_id" {
  value       = google_bigquery_dataset.crypto_analytics.dataset_id
  description = "ID du dataset BigQuery"
}

output "bigquery_tables" {
  value = {
    historical_raw      = google_bigquery_table.historical_raw.table_id
    market_data_unified = google_bigquery_table.market_data_unified.table_id # ← Corrigé
  }
  description = "Tables BigQuery créées"
}