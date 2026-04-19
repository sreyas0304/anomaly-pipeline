terraform {
  backend "s3" {
    bucket         = "fleet-telemetry-tfstate"
    key            = "fleet-telemetry/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "fleet-telemetry-tf-lock"
    encrypt        = true
  }
}
