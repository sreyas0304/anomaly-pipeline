resource "aws_s3_bucket" "datalake" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    id     = "raw-tiering"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 365
    }
  }
}

resource "aws_s3_object" "raw_prefix" {
  bucket  = aws_s3_bucket.datalake.id
  key     = "raw/"
  content = ""
}

resource "aws_s3_object" "athena_results_prefix" {
  bucket  = aws_s3_bucket.datalake.id
  key     = "athena-results/"
  content = ""
}

resource "aws_s3_object" "errors_prefix" {
  bucket  = aws_s3_bucket.datalake.id
  key     = "errors/"
  content = ""
}
