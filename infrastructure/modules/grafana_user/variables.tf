variable "user_name" {
  description = "Name of the Grafana read-only IAM user"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 data-lake bucket (for Athena result writes)"
  type        = string
}
