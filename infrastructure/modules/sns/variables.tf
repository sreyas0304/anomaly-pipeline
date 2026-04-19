variable "topic_name" {
  description = "Name of the SNS topic"
  type        = string
}

variable "alert_email" {
  description = "Email address for the SNS email subscription"
  type        = string
}
