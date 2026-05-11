# Infra

Terraform config for the two R2 buckets Melilo uses.

## One-time setup

1. Install Terraform (>= 1.5).
2. Create a Cloudflare API token with **Account → Workers R2 Storage: Edit**.
3. Export credentials:

   ```bash
   export CLOUDFLARE_API_TOKEN=...
   export TF_VAR_cloudflare_account_id=...   # from the Cloudflare dashboard
   ```

4. Initialize and apply:

   ```bash
   cd infra
   terraform init
   terraform apply
   ```

This creates `melilo-legal-source` and `melilo-pairs`. Override the names with
`-var source_bucket_name=...` if you need different ones.

## Access keys

Terraform provisions buckets but does **not** create R2 access keys (the
provider doesn't expose that resource yet). After `apply`:

1. Cloudflare dashboard → R2 → Manage R2 API Tokens → Create API token.
2. Scope it to the two buckets above with read/write.
3. Drop the access key id and secret into `.env` at the repo root.
