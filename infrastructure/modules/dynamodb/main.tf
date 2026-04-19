resource "aws_dynamodb_table" "anomalies" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "vin"
  range_key    = "timestamp"

  attribute {
    name = "vin"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "severity"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  global_secondary_index {
    name            = "severity-timestamp-index"
    hash_key        = "severity"
    range_key       = "timestamp"
    projection_type = "ALL"
  }
}
