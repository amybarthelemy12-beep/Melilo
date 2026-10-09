output "deployment_environment" {
  value = var.deployment_environment
}

output "source_bucket_name" {
  value = cloudflare_r2_bucket.source.name
}

output "pairs_bucket_name" {
  value = cloudflare_r2_bucket.pairs.name
}

output "r2_endpoint" {
  value = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}

output "deployment_metadata" {
  value = terraform_data.deployment_metadata.output
}

output "configured_buckets" {
  value = {
    source = cloudflare_r2_bucket.source.name
    pairs  = cloudflare_r2_bucket.pairs.name
  }
}
