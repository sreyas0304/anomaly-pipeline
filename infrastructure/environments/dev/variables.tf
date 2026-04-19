variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "fleet-telemetry"
}

variable "stream_name" {
  description = "Name of the Kinesis data stream"
  type        = string
  default     = "fleet-telemetry-stream"
}

variable "shard_count" {
  description = "Number of shards for the Kinesis stream"
  type        = number
  default     = 1
}

variable "retention_period" {
  description = "Data retention period in hours"
  type        = number
  default     = 24
}

variable "alert_email" {
  description = "Email address for SNS CRITICAL anomaly alerts"
  type        = string
}

variable "account_id" {
  description = "AWS account ID used to construct the globally-unique S3 bucket name"
  type        = string
}
