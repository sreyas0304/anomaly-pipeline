variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "kinesis_stream_arn" {
  description = "ARN of the Kinesis stream to trigger the Lambda"
  type        = string
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB anomalies table (injected as env var)"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB anomalies table (for IAM policy)"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the SNS alerts topic (injected as env var)"
  type        = string
}

variable "environment" {
  description = "Deployment environment (injected as env var)"
  type        = string
}

variable "anomaly_ttl_days" {
  description = "Number of days before anomaly records expire in DynamoDB"
  type        = number
  default     = 90
}
