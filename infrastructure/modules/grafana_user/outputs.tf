output "access_key_id" {
  description = "Access key ID for the Grafana IAM user"
  value       = aws_iam_access_key.grafana.id
}

output "secret_access_key" {
  description = "Secret access key for the Grafana IAM user"
  value       = aws_iam_access_key.grafana.secret
  sensitive   = true
}
