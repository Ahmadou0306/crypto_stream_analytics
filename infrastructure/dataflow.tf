output "dataflow_launch_command" {
  value = <<-EOT
cd ../dataflow

python pipeline.py \
  --runner=DataflowRunner \
  --extra_package=dist/crypto-stream-dataflow-1.0.0.tar.gz \
  --project=${var.project_id} \
  --region=${var.region} \
  --subscription=${google_pubsub_subscription.crypto_klines_dataflow.name} \
  --dataset=${google_bigquery_dataset.crypto_analytics.dataset_id} \
  --table=${google_bigquery_table.market_data_unified.table_id} \
  --temp_location=gs://${google_storage_bucket.dataflow_bucket.name}/temp \
  --staging_location=gs://${google_storage_bucket.dataflow_bucket.name}/staging \
  --service_account_email=${google_service_account.dataflow_stream_sa.email} \
  --streaming
  EOT
}