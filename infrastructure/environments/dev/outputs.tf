# ── Session 1 outputs (unchanged) ─────────────────────────────────────────────

output "stream_arn" {
  description = "ARN of the Kinesis data stream"
  value       = module.kinesis.stream_arn
}

output "stream_name" {
  description = "Name of the Kinesis data stream"
  value       = module.kinesis.stream_name
}

output "producer_access_key_id" {
  description = "Access key ID for the fleet telemetry producer"
  value       = module.iam.access_key_id
  sensitive   = true
}

output "producer_secret_access_key" {
  description = "Secret access key for the fleet telemetry producer"
  value       = module.iam.secret_access_key
  sensitive   = true
}

# ── Session 2 outputs ─────────────────────────────────────────────────────────

output "s3_datalake_bucket_name" {
  description = "Name of the S3 data-lake bucket"
  value       = module.s3_datalake.bucket_name
}

output "s3_datalake_bucket_arn" {
  description = "ARN of the S3 data-lake bucket"
  value       = module.s3_datalake.bucket_arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB anomalies table"
  value       = module.dynamodb.table_name
}

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = module.sns.topic_arn
}

output "grafana_access_key_id" {
  description = "Access key ID for the Grafana IAM user"
  value       = module.grafana_user.access_key_id
  sensitive   = true
}

output "grafana_secret_access_key" {
  description = "Secret access key for the Grafana IAM user"
  value       = module.grafana_user.secret_access_key
  sensitive   = true
}
