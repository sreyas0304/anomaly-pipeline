output "database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.this.name
}

output "crawler_name" {
  description = "Name of the Glue crawler"
  value       = aws_glue_crawler.this.name
}
