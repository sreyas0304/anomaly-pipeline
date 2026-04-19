resource "aws_iam_user" "producer" {
  name = var.user_name

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_iam_access_key" "producer" {
  user = aws_iam_user.producer.name
}

resource "aws_iam_user_policy" "producer_kinesis" {
  name = "${var.user_name}-kinesis-policy"
  user = aws_iam_user.producer.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords",
          "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary"
        ]
        Resource = var.kinesis_stream_arn
      }
    ]
  })
}
