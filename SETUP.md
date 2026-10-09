# Melilo setup guide

This repo now includes infrastructure automation, validation, and local runtime helpers for Cloudflare R2 + Neon + local Ollama development.

## Prerequisites

- Terraform 1.5+
- Python 3.10+
- Cloudflare account with R2 access
- Neon database URL
- Optional: Ollama installed locally

## 1) Cloudflare + Neon setup

1. Create a Cloudflare API token with R2 access to the target account.
2. Copy `.env.example` to `.env` and fill in at least:

   ```bash
   cp .env.example .env
   ```

3. Add:

   - `CLOUDFLARE_API_TOKEN`
   - `TF_VAR_cloudflare_account_id`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_ENDPOINT`
   - `NEON_DATABASE_URL`

## 2) Terraform setup

```bash
./scripts/setup_infra.sh
```

This will:

- validate Terraform is installed
- validate the Cloudflare token/account id
- initialize Terraform
- apply the infrastructure
- write output values into `.env`
- validate the final environment before continuing

If you need separate buckets for dev/prod, export before running:

```bash
export TF_VAR_deployment_environment=prod
export TF_VAR_source_bucket_name=melilo-legal-source-prod
export TF_VAR_pairs_bucket_name=melilo-pairs-prod
./scripts/setup_infra.sh
```

## 3) Environment validation

```bash
python scripts/validate_env.py --env-file .env --strict
```

This checks required variables before any infrastructure or runtime actions begin.

## 4) Local runtime setup

```bash
./scripts/start_local_stack.sh
```

This is meant for local development and includes optional Ollama model setup.

## 5) Health and status checks

```bash
python scripts/infra_status.py --env-file .env --json
```

The script emits a JSON summary covering:

- bucket existence
- Cloudflare API connectivity
- manifest metadata
- versioning status
- deployment metadata

## 6) Rollback notes

- Delete Terraform-created buckets in the Cloudflare dashboard only after verifying nothing critical depends on them.
- Keep `.env` values version-controlled only as examples; do not commit real secrets.
- Since Cloudflare R2 lifecycle and retention behavior can differ by provider/API exposure, use `scripts/infra_status.py` as the source of truth for sanity-checking the deployed setup.

## Troubleshooting

- If Terraform validate fails, confirm `CLOUDFLARE_API_TOKEN` and `TF_VAR_cloudflare_account_id` are set.
- If Ollama fails, ensure the service is installed and the model has been pulled.
- If Neon validation fails, confirm the host is reachable on port 5432 and the SSL mode is correctly configured in `NEON_DATABASE_URL`.
- If `.env` generation appears stale, re-run `./scripts/setup_infra.sh`.
