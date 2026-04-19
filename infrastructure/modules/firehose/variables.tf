variable "delivery_stream_name" {
  description = "Name of the Kinesis Firehose delivery stream"
  type        = string
}

variable "kinesis_stream_arn" {
  description = "ARN of the source Kinesis data stream"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the destination S3 data-lake bucket"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the destination S3 data-lake bucket (for policy resources)"
  type        = string
}
