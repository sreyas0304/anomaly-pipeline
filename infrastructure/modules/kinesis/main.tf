resource "aws_kinesis_stream" "this" {
  name             = var.stream_name
  shard_count      = var.shard_count
  retention_period = var.retention_period

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
