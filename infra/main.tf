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
  # Set CLOUDFLARE_API_TOKEN in your env. The token needs:
  #   - Account: Workers R2 Storage: Edit
  api_token = var.cloudflare_api_token
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account that will own the R2 buckets."
}

variable "source_bucket_name" {
  type    = string
  default = "melilo-legal-source"
}

variable "pairs_bucket_name" {
  type    = string
  default = "melilo-pairs"
}

variable "location" {
  type        = string
  default     = "wnam"
  description = "R2 location hint: wnam, enam, weur, eeur, apac, oc."
}

resource "cloudflare_r2_bucket" "source" {
  account_id = var.cloudflare_account_id
  name       = var.source_bucket_name
  location   = var.location
}

resource "cloudflare_r2_bucket" "pairs" {
  account_id = var.cloudflare_account_id
  name       = var.pairs_bucket_name
  location   = var.location
}

output "source_bucket" {
  value = cloudflare_r2_bucket.source.name
}

output "pairs_bucket" {
  value = cloudflare_r2_bucket.pairs.name
}

output "r2_endpoint" {
  value = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}
