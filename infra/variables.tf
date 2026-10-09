variable "cloudflare_api_token" {
  type        = string
  description = "Cloudflare API token with account-level R2 permissions."
  default     = ""
  sensitive   = true
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account ID that owns the R2 buckets."
  default     = ""
}

variable "deployment_environment" {
  type        = string
  description = "Terraform environment label (dev/prod)."
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod", "staging"], lower(var.deployment_environment))
    error_message = "deployment_environment must be one of: dev, prod, staging."
  }
}

variable "source_bucket_name" {
  type        = string
  description = "Bucket used for source/legal docs and if necessary public archive access."
  default     = "melilo-legal-source"
}

variable "pairs_bucket_name" {
  type        = string
  description = "Bucket used to store generated JSONL pairs and intermediate outputs."
  default     = "melilo-pairs"
}

variable "location" {
  type        = string
  description = "Cloudflare R2 location hint (for example: wnam, enam, weur, eeur, apac, oc)."
  default     = "wnam"
}

variable "object_expiration_days" {
  type        = number
  description = "Lifecycle retention policy in days for object cleanup."
  default     = 365
}

variable "retention_days" {
  type        = number
  description = "Optional retention window for archive artifacts."
  default     = 90
}
