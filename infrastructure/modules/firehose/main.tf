# ── IAM Role for Firehose ─────────────────────────────────────────────────────

resource "aws_iam_role" "firehose" {
  name = "dev-fleet-telemetry-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose_policy" {
  name = "dev-fleet-telemetry-firehose-policy"
  role = aws_iam_role.firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:DescribeStream",
          "kinesis:ListShards",
          "kinesis:ListStreams"
        ]
        Resource = var.kinesis_stream_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# ── Delivery Stream ───────────────────────────────────────────────────────────

resource "aws_kinesis_firehose_delivery_stream" "raw" {
  name        = var.delivery_stream_name
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = var.kinesis_stream_arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn           = aws_iam_role.firehose.arn
    bucket_arn         = var.s3_bucket_arn
    buffering_size     = 64
    buffering_interval = 60
    compression_format = "GZIP"

    prefix              = "raw/fleet_group=!{partitionKeyFromQuery:fleet_group}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/!{firehose:error-output-type}/"

    dynamic_partitioning_configuration {
      enabled        = true
      retry_duration = 300
    }

    processing_configuration {
      enabled = true

      processors {
        type = "MetadataExtraction"

        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }

        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{fleet_group:.vehicle.fleet_group}"
        }
      }

      processors {
        type = "AppendDelimiterToRecord"

        parameters {
          parameter_name  = "Delimiter"
          parameter_value = "\\n"
        }
      }
    }
  }
}
