# Scheduled Query pour dim_dates (quotidienne)
resource "google_bigquery_data_transfer_config" "update_dim_dates_daily" {
  display_name   = "Update dim_dates daily"
  location       = var.region
  data_source_id = "scheduled_query"

  schedule = "every day 00:10"
  schedule_options {
    disable_auto_scheduling = false
  }

  destination_dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id

  params = {
    query                           = file("${path.root}/../bigquery/dim_dates.sql")
    destination_table_name_template = "dim_dates"
    write_disposition               = "WRITE_TRUNCATE"
  }

  depends_on = [google_bigquery_table.dim_dates]
}

# Scheduled Query pour dim_symboles (mensuelle)
resource "google_bigquery_data_transfer_config" "update_dim_symboles_monthly" {
  display_name   = "Update dim_symboles monthly"
  location       = var.region
  data_source_id = "scheduled_query"

  schedule = "1 of month 00:10"
  schedule_options {
    disable_auto_scheduling = false
  }

  destination_dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id

  params = {
    query                           = file("${path.root}/../bigquery/dim_symboles.sql")
    destination_table_name_template = "dim_symboles"
    write_disposition               = "WRITE_TRUNCATE"
  }

  depends_on = [google_bigquery_table.dim_symboles]
}

# Scheduled Query pour dim_hours (manuelle uniquement)
resource "google_bigquery_data_transfer_config" "populate_dim_hours_manual" {
  display_name   = "Populate dim_hours (manual)"
  location       = var.region
  data_source_id = "scheduled_query"

  schedule = "every day 00:00"
  schedule_options {
    disable_auto_scheduling = true # s execute manuellement via l'interface
  }

  destination_dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id

  params = {
    query = file("${path.root}/../bigquery/dim_hours.sql")
  }

  depends_on = [google_bigquery_table.dim_hours]
}

# Scheduled Query pour transform_historical (manuelle uniquement)
resource "google_bigquery_data_transfer_config" "trigger_transform_historical_manual" {
  display_name   = "Transform historical data (manual)"
  location       = var.region
  data_source_id = "scheduled_query"

  schedule = "every day 00:00"
  schedule_options {
    disable_auto_scheduling = true # s execute manuellement via l'interface
  }

  destination_dataset_id = google_bigquery_dataset.crypto_analytics.dataset_id

  params = {
    query                           = file("${path.root}/../bigquery/transform_historical.sql")
    destination_table_name_template = "market_data_unified"
    write_disposition               = "WRITE_APPEND"
  }

  depends_on = [google_bigquery_table.market_data_unified]
}