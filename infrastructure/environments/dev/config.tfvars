aws_region       = "us-east-1"
environment      = "dev"
project_name     = "fleet-telemetry"
stream_name      = "fleet-telemetry-stream"
shard_count      = 1
retention_period = 24
alert_email      = "srsawant.iu@gmail.com"
account_id       = "481665108850" # replace: aws sts get-caller-identity --query Account --output text
