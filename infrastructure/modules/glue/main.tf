# ── IAM Role for Glue ─────────────────────────────────────────────────────────

resource "aws_iam_role" "glue" {
  name = "dev-fleet-telemetry-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3" {
  name = "dev-fleet-telemetry-glue-s3"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ]
      Resource = [
        var.s3_bucket_arn,
        "${var.s3_bucket_arn}/*"
      ]
    }]
  })
}

# ── Glue Catalog Resources ────────────────────────────────────────────────────

resource "aws_glue_catalog_database" "this" {
  name = var.glue_database_name
}

resource "aws_glue_classifier" "json" {
  name = var.classifier_name

  json_classifier {
    json_path = "$[*]"
  }
}

resource "aws_glue_crawler" "this" {
  name          = var.crawler_name
  database_name = aws_glue_catalog_database.this.name
  role          = aws_iam_role.glue.arn
  classifiers   = [aws_glue_classifier.json.name]
  schedule      = "cron(0 * * * ? *)"

  s3_target {
    path = "s3://${var.s3_bucket_name}/raw/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
      Tables     = { AddOrUpdateBehavior = "MergeNewColumns" }
    }
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
  })
}
