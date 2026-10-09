# Infra

Terraform config for the R2 buckets Melilo uses, plus the local validation and bootstrap tooling that wraps it.

## Current state and Cloudflare nuances

The repo uses Cloudflare R2 through the official Terraform provider. The current provider supports bucket creation, account binding, and a subset of bucket settings, but some operational controls such as bucket lifecycle / retention policy and versioning are not always exposed as first-class Terraform arguments in the provider.

For that reason, this repo intentionally separates:

- Terraform-managed resource creation and naming
- script-managed runtime validation and environment bootstrap
- operational checks for versioning, bucket existence, and retention enforcement via `scripts/infra_status.py`

This leaves the setup reproducible while still handling Cloudflare's practical API limits in a safe, explicit way.

## One-time setup

1. Install Terraform (>= 1.5)
2. Create a Cloudflare API token with account-level R2 permissions
3. Export credentials:

   ```bash
   export CLOUDFLARE_API_TOKEN=...
   export TF_VAR_cloudflare_account_id=...
   ```

4. Initialize and apply:

   ```bash
   cd infra
   terraform init
   terraform apply
   ```

5. Or use the repo wrapper script:

   ```bash
   ./scripts/setup_infra.sh
   ```

## Separate dev / prod bucket patterns

The repo supports environment-specific bucket names via variables:

```bash
export TF_VAR_deployment_environment=dev
export TF_VAR_source_bucket_name=melilo-legal-source-dev
export TF_VAR_pairs_bucket_name=melilo-pairs-dev
```

or by passing the values directly when applying Terraform:

```bash
cd infra
terraform apply \
  -var='deployment_environment=prod' \
  -var='source_bucket_name=melilo-legal-source-prod' \
  -var='pairs_bucket_name=melilo-pairs-prod'
```

## Access keys

Terraform provisions the buckets but does not create the R2 access keys themselves. After apply:

1. Cloudflare dashboard → R2 → Manage R2 API Tokens → Create API token
2. Scope it to the buckets being created
3. Save the key values into `.env` at the repo root

## Validation scripts

```bash
python scripts/validate_env.py --env-file .env
python scripts/infra_status.py --env-file .env --json
```

## Local startup

```bash
./scripts/start_local_stack.sh
```

This will:

- check Ollama installation
- pull or verify the configured Olmo model
- generate local `.env` defaults if needed
- print the next commands to run

## Notes on policy controls

Operational retention and versioning controls are validated via:

- `scripts/infra_status.py`
- `infra/manifest.json`
- the generated `.env` values and deployment metadata

Cloudflare can impose API limits or partial support for some lifecycle settings; this repo treats those as runtime checks instead of assuming the provider exposes all controls natively.
