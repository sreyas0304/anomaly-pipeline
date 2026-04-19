variable "stream_name" {
  description = "Name of the Kinesis data stream"
  type        = string
}

variable "shard_count" {
  description = "Number of shards for the stream"
  type        = number
  default     = 1
}

variable "retention_period" {
  description = "Data retention period in hours"
  type        = number
  default     = 24
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
}
