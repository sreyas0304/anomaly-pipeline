variable "glue_database_name" {
  description = "Name of the Glue catalog database (underscores, no hyphens)"
  type        = string
}

variable "classifier_name" {
  description = "Name of the Glue JSON classifier"
  type        = string
}

variable "crawler_name" {
  description = "Name of the Glue crawler"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 data-lake bucket"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 data-lake bucket (used to build S3 target path)"
  type        = string
}
