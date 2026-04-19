output "access_key_id" {
  description = "Access key ID for the producer IAM user"
  value       = aws_iam_access_key.producer.id
}

output "secret_access_key" {
  description = "Secret access key for the producer IAM user"
  value       = aws_iam_access_key.producer.secret
  sensitive   = true
}

output "user_arn" {
  description = "ARN of the producer IAM user"
  value       = aws_iam_user.producer.arn
}

output "user_name" {
  description = "Name of the producer IAM user"
  value       = aws_iam_user.producer.name
}
