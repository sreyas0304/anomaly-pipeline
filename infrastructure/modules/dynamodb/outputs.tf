output "table_name" {
  description = "Name of the DynamoDB anomalies table"
  value       = aws_dynamodb_table.anomalies.name
}

output "table_arn" {
  description = "ARN of the DynamoDB anomalies table"
  value       = aws_dynamodb_table.anomalies.arn
}
