# Melilo Operation Checklist

This is a copy/paste operational checklist for setting up, validating, and running the local and infra stack.

## 1) Prerequisites

- Terraform >= 1.5 installed
- Python 3.10+ installed
- Cloudflare account with R2 access
- Neon database URL ready
- Optional: Ollama installed locally

## 2) Initial environment file

```bash
cp .env.example .env
```

Then edit `.env` and fill in:

- `CLOUDFLARE_API_TOKEN`
- `TF_VAR_cloudflare_account_id`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_PUBLIC_BUCKET`
- `R2_INTERNAL_BUCKET`
- `R2_MELILO_BUCKET`
- `NEON_DATABASE_URL`
- `MELILO_BACKEND`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TRANSLATOR_MODEL`

## 3) Validate environment

```bash
python scripts/validate_env.py --env-file .env --strict
```

If it fails, fix the missing values and rerun.

## 4) Bootstrap infra

```bash
./scripts/setup_infra.sh
```

This script will:
- validate Terraform
- ensure credentials are present
- initialize Terraform
- apply Cloudflare R2 infrastructure
- populate `.env` with generated bucket metadata
- run final validation

## 5) Local runtime startup

```bash
./scripts/start_local_stack.sh
```

This script will:
- check if Ollama is installed
- verify the configured model is available
- pull the model if needed
- print suggested next commands

## 6) Check infra health

```bash
python scripts/infra_status.py --env-file .env --json
```

This is the quick operational check to confirm:
- bucket exists
- Cloudflare connection works
- deployment metadata is sane
- versioning metadata is present

## 7) Typical valid setup sequence

```bash
cp .env.example .env
python scripts/validate_env.py --env-file .env --strict
./scripts/setup_infra.sh
./scripts/start_local_stack.sh
python scripts/infra_status.py --env-file .env --json
```

## 8) Typical troubleshooting flow

```bash
python scripts/validate_env.py --env-file .env --strict
python scripts/infra_status.py --env-file .env --json
./scripts/setup_infra.sh
./scripts/start_local_stack.sh
```

## 9) Bucket naming and environment separation

You may want separate dev vs prod buckets:

```bash
export TF_VAR_deployment_environment=prod
export TF_VAR_source_bucket_name=melilo-legal-source-prod
export TF_VAR_pairs_bucket_name=melilo-pairs-prod
./scripts/setup_infra.sh
```

## 10) Rollback / clean recovery notes

- Do not commit real secrets to git
- If infrastructure names appear wrong, rerun `./scripts/setup_infra.sh`
- If a token is invalid, rotate it in Cloudflare and update `.env`
- If local model is missing, run `ollama pull olmo-3:7b-instruct`
- If R2 bucket status fails, verify token permissions and account ID

## 11) Notes on intended usage

This stack is meant to be:
- local-friendly
- CI-safe
- clear for onboarding
- deterministic for infrastructure setup
- easy to validate before running data jobs

## 12) Fast path command set

```bash
cp .env.example .env
python scripts/validate_env.py --env-file .env --strict
./scripts/setup_infra.sh
./scripts/start_local_stack.sh
python scripts/infra_status.py --env-file .env --json
```
