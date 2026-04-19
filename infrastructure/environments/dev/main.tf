terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  bucket_name = "dev-fleet-telemetry-lake-${var.account_id}"
}

# ── Session 1: Existing resources (names unchanged) ───────────────────────────

module "kinesis" {
  source = "../../modules/kinesis"

  stream_name      = var.stream_name
  shard_count      = var.shard_count
  retention_period = var.retention_period
  environment      = var.environment
  project_name     = var.project_name
}

module "iam" {
  source = "../../modules/iam"

  user_name          = "fleet-telemetry-producer"
  kinesis_stream_arn = module.kinesis.stream_arn
  environment        = var.environment
  project_name       = var.project_name
}

# ── Session 2: New resources (dev- prefix) ────────────────────────────────────

module "s3_datalake" {
  source = "../../modules/s3_datalake"

  bucket_name = local.bucket_name
}

module "sns" {
  source = "../../modules/sns"

  topic_name  = "dev-fleet-telemetry-alerts"
  alert_email = var.alert_email
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  table_name = "dev-fleet-anomalies"
}

module "firehose" {
  source = "../../modules/firehose"

  delivery_stream_name = "dev-fleet-telemetry-raw-delivery"
  kinesis_stream_arn   = module.kinesis.stream_arn
  s3_bucket_arn        = module.s3_datalake.bucket_arn
  s3_bucket_name       = local.bucket_name
}

module "glue" {
  source = "../../modules/glue"

  glue_database_name = "dev_fleet_telemetry_db"
  classifier_name    = "dev-fleet-telemetry-json-classifier"
  crawler_name       = "dev-fleet-telemetry-crawler"
  s3_bucket_arn      = module.s3_datalake.bucket_arn
  s3_bucket_name     = local.bucket_name
}

module "lambda_detector" {
  source = "../../modules/lambda_detector"

  function_name       = "dev-fleet-telemetry-detector"
  kinesis_stream_arn  = module.kinesis.stream_arn
  dynamodb_table_name = module.dynamodb.table_name
  dynamodb_table_arn  = module.dynamodb.table_arn
  sns_topic_arn       = module.sns.topic_arn
  environment         = var.environment
  anomaly_ttl_days    = 90
}

module "grafana_user" {
  source = "../../modules/grafana_user"

  user_name     = "dev-fleet-telemetry-grafana"
  s3_bucket_arn = module.s3_datalake.bucket_arn
}
