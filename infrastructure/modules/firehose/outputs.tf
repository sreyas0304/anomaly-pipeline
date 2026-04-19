output "delivery_stream_arn" {
  description = "ARN of the Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.raw.arn
}

output "delivery_stream_name" {
  description = "Name of the Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.raw.name
}
