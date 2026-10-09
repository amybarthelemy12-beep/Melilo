terraform {
  required_version = ">= 1.5"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

locals {
  deployment_tags = {
    project     = "melilo"
    environment = var.deployment_environment
    managed_by  = "terraform"
    owner       = "melilo"
  }

  source_bucket_name = var.source_bucket_name
  pairs_bucket_name  = var.pairs_bucket_name
}

resource "cloudflare_r2_bucket" "source" {
  account_id = var.cloudflare_account_id
  name       = local.source_bucket_name
  location   = var.location
}

resource "cloudflare_r2_bucket" "pairs" {
  account_id = var.cloudflare_account_id
  name       = local.pairs_bucket_name
  location   = var.location
}

resource "terraform_data" "deployment_metadata" {
  input = {
    infrastructure_version = "2026.10.09"
    deployment_environment = var.deployment_environment
    source_bucket_name     = local.source_bucket_name
    pairs_bucket_name      = local.pairs_bucket_name
    location               = var.location
    versioning_enabled     = true
    object_expiration_days = var.object_expiration_days
    retention_days         = var.retention_days
  }
}
