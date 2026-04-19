variable "user_name" {
  description = "Name of the IAM user"
  type        = string
}

variable "kinesis_stream_arn" {
  description = "ARN of the Kinesis stream to grant access to"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
}
