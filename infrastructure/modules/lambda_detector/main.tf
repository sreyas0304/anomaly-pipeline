# ── Zip source ────────────────────────────────────────────────────────────────
# path.root = infrastructure/environments/dev  (where terraform is run from)
# ../../lambda_src resolves to infrastructure/lambda_src

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.root}/../../lambda_src/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

# ── IAM Role ─────────────────────────────────────────────────────────────────

resource "aws_iam_role" "lambda" {
  name = "dev-fleet-telemetry-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_kinesis" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaKinesisExecutionRole"
}

resource "aws_iam_role_policy" "lambda_dynamo_sns" {
  name = "dev-fleet-telemetry-lambda-dynamo-sns"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.sns_topic_arn
      }
    ]
  })
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 30
}

# ── Lambda Function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "detector" {
  function_name    = var.function_name
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  memory_size      = 256
  timeout          = 60

  environment {
    variables = {
      DYNAMODB_TABLE   = var.dynamodb_table_name
      SNS_TOPIC_ARN    = var.sns_topic_arn
      ENVIRONMENT      = var.environment
      ANOMALY_TTL_DAYS = tostring(var.anomaly_ttl_days)
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# ── Kinesis Event Source Mapping ──────────────────────────────────────────────

resource "aws_lambda_event_source_mapping" "kinesis" {
  event_source_arn                   = var.kinesis_stream_arn
  function_name                      = aws_lambda_function.detector.arn
  starting_position                  = "LATEST"
  batch_size                         = 250
  maximum_batching_window_in_seconds = 10
  bisect_batch_on_function_error     = true
  maximum_retry_attempts             = 3
  maximum_record_age_in_seconds      = 3600

  function_response_types = ["ReportBatchItemFailures"]
}
