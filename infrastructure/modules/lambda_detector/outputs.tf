output "function_arn" {
  description = "ARN of the Lambda detector function"
  value       = aws_lambda_function.detector.arn
}

output "function_name" {
  description = "Name of the Lambda detector function"
  value       = aws_lambda_function.detector.function_name
}
