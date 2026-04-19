resource "aws_iam_user" "grafana" {
  name = var.user_name
}

resource "aws_iam_access_key" "grafana" {
  user = aws_iam_user.grafana.name
}

resource "aws_iam_user_policy" "grafana_read" {
  name = "${var.user_name}-read-policy"
  user = aws_iam_user.grafana.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Athena requires Resource: * — no resource-level restrictions available
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup",
          "athena:ListWorkGroups",
          "athena:ListDatabases",
          "athena:ListTableMetadata",
          "athena:GetTableMetadata"
        ]
        Resource = "*"
      },
      {
        # Glue catalog requires Resource: * for cross-partition compatibility
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
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
