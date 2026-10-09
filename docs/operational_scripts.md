# Melilo Operations & Infrastructure Documentation

This document is the command and operations reference for every script, environment task, and operational workflow needed to run and maintain the Melilo infrastructure stack.

## Scope

This repo includes support for:

- Cloudflare R2 bucket provisioning and validation
- Terraform bootstrap and state management
- Neon/Postgres connectivity validation
- Local runtime preparation for Ollama and OpenAI-compatible backends
- Environment validation before any run
- CI/CD validation
- Local development and operational checks
- Versioning, retention, and status reporting

## Core operational goals

1. Reproducible infrastructure setup
2. Safe environment validation before all actions
3. Clear local development flow for Ollama + OpenAI-compatible services
4. Simple operational status checks for R2 / Neon / deployment metadata
5. CI/CD guardrails for the repo

## Environment files and defaults

Primary files:

- `.env.example` — template for required variables
- `.env` — local environment for actual secrets and configuration
- `infra/manifest.json` — deployment metadata / versioning metadata

Mandatory variables:

- `CLOUDFLARE_API_TOKEN`
- `TF_VAR_cloudflare_account_id`
- `TF_VAR_deployment_environment`
- `TF_VAR_source_bucket_name`
- `TF_VAR_pairs_bucket_name`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `R2_PUBLIC_BUCKET`
- `R2_INTERNAL_BUCKET`
- `R2_MELILO_BUCKET`
- `R2_MELILO_ENDPOINT`
- `NEON_DATABASE_URL`
- `MELILO_BACKEND`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TRANSLATOR_MODEL`

## Scripts reference

### 1) `scripts/setup_infra.sh`

Purpose:
- bootstrap Terraform
- validate credentials and environment
- ensure `.env` has the required values
- initialize/apply the created infrastructure
- run a post-apply validation

Usage:

```bash
./scripts/setup_infra.sh
```

Optional overrides:

```bash
ENV_FILE=.env ./scripts/setup_infra.sh
TF_VAR_deployment_environment=prod TF_VAR_source_bucket_name=melilo-legal-source-prod TF_VAR_pairs_bucket_name=melilo-pairs-prod ./scripts/setup_infra.sh
```

What it does:
- checks `terraform` and `python3` exist
- verifies `CLOUDFLARE_API_TOKEN` and `TF_VAR_cloudflare_account_id`
- copies `.env.example` to `.env` if missing
- runs `terraform init`, `terraform validate`, `terraform apply`
- writes Terraform outputs back into `.env`
- runs `python scripts/validate_env.py --strict`
- performs a Neon connectivity probe if a `NEON_DATABASE_URL` is present

When to use:
- first-time setup
- re-running infrastructure after changing buckets or environment names
- refreshing configuration after provider or account changes

### 2) `scripts/validate_env.py`

Purpose:
- fail early on invalid or missing required environment values
- provide clear, actionable validation output

Usage:

```bash
python scripts/validate_env.py --env-file .env
python scripts/validate_env.py --env-file .env --strict
```

Behavior:
- reads environment variables from OS and `.env`
- checks required keys for config and runtime readiness
- exits nonzero if variables are missing

When to use:
- before running Terraform or local jobs
- before CI/CD deploy checks
- before any backfill, data job, or model run

### 3) `scripts/start_local_stack.sh`

Purpose:
- create local defaults when the environment is missing
- optionally verify local Ollama installation and model availability
- print next-step commands for the user

Usage:

```bash
./scripts/start_local_stack.sh
```

Behavior:
- creates a default `.env` if missing
- checks whether Ollama is installed
- verifies the configured local model is available
- prints suggested next commands

When to use:
- local dev bootstrapping
- starting a local model stack before backfills or inference

### 4) `scripts/infra_status.py`

Purpose:
- check bucket existence and health through Cloudflare APIs
- read deployment metadata from `infra/manifest.json`
- surface basic operational status in CLI or JSON mode

Usage:

```bash
python scripts/infra_status.py --env-file .env
python scripts/infra_status.py --env-file .env --json
```

Output:
- bucket existence status
- versioning flag status
- manifest metadata
- Cloudflare API payload if available

When to use:
- daily operational checks
- deployment verification
- troubleshooting R2 connectivity or naming issues

### 5) `infra/README.md`

Purpose:
- Terraform-specific usage and Cloudflare notes
- guidance for bucket naming and environment-specific deployments

Usage:
- read when provisioning infrastructure or diagnosing Terraform issues

### 6) `SETUP.md`

Purpose:
- high-level setup guide for Cloudflare, Neon, validation, status checks, rollback, and troubleshooting

Usage:
- onboarding and deployment reference for engineers

### 7) `Dockerfile`

Purpose:
- standard Python app container build for local or CI validation

Usage:

```bash
docker build -t melilo .
```

### 8) `docker-compose.yml`

Purpose:
- local dev convenience stack with app + Ollama service

Usage:

```bash
docker compose up --build
```

### 9) `.github/workflows/infra-check.yml`

Purpose:
- CI validation for environment config and Terraform syntax

Usage:
- automatic on push / PR / manual dispatch

## Terraform reference

Infrastructure directory:

- `infra/main.tf`
- `infra/variables.tf`
- `infra/outputs.tf`
- `infra/manifest.json`

Core Terraform responsibilities:
- create source bucket
- create pairs bucket
- bind environment metadata
- expose output values for use by scripts

Typical commands:

```bash
cd infra
terraform init
terraform validate
terraform plan
terraform apply
terraform output -json
```

## Cloudflare R2 operational model

This repo assumes the following operational pattern:

- Cloudflare account owns the target buckets
- Terraform creates or manages bucket names and metadata
- runtime scripts validate the credentials and environment values
- `scripts/infra_status.py` is the health-check and operational QA tool
- R2 API access keys are still created in the Cloudflare dashboard, then stored in `.env`

## Neon operational model

This repo expects:

- a valid PostgreSQL connection string in `NEON_DATABASE_URL`
- SSL enabled as required by Neon
- database connectivity checked before longer-running jobs begin

Typical validation:

```bash
python scripts/validate_env.py --env-file .env
```

## Local Ollama / model workflow

This repo supports a local OpenAI-compatible backend pointed at Ollama:

- `MELILO_BACKEND=openai`
- `OPENAI_BASE_URL=http://localhost:11434/v1`
- `OPENAI_API_KEY=ollama`
- `OPENAI_MODEL=olmo-3:7b-instruct`

Typical commands:

```bash
./scripts/start_local_stack.sh
ollama pull olmo-3:7b-instruct
```

## Recommended routine

For a fresh local environment:

```bash
cp .env.example .env
# fill in required values
python scripts/validate_env.py --env-file .env --strict
./scripts/setup_infra.sh
python scripts/infra_status.py --env-file .env --json
./scripts/start_local_stack.sh
```

For a recurring operational check:

```bash
python scripts/validate_env.py --env-file .env
python scripts/infra_status.py --env-file .env --json
```

## Troubleshooting quick reference

### Terraform fails validation

- confirm `CLOUDFLARE_API_TOKEN` exists
- confirm `TF_VAR_cloudflare_account_id` is set
- re-run `terraform init` and `terraform validate`

### `.env` missing required values

- copy `.env.example` and fill in values
- rerun `python scripts/validate_env.py --env-file .env --strict`

### R2 status check fails

- confirm the token has access to the account
- confirm bucket names match the environment
- verify `R2_MELILO_BUCKET` and Cloudflare account settings

### Neon check fails

- confirm `NEON_DATABASE_URL` is syntactically valid
- confirm host reachability on port 5432
- confirm SSL mode is correctly included in the URL

### Ollama not available

- install Ollama locally
- pull the target model
- verify `OPENAI_BASE_URL` points to the Ollama API server

## Operational safety rules

1. Never commit actual secrets to the repository.
2. Validate before infrastructure and backfill runs.
3. Use `.env.example` as the safe template.
4. Treat `scripts/infra_status.py` as the operational health check.
5. Keep environment-specific bucket names explicit.
6. Keep deployment metadata in `infra/manifest.json` for monitoring and audit trails.

## Useful command cheat sheet

```bash
# validate env
python scripts/validate_env.py --env-file .env --strict

# provision infra
./scripts/setup_infra.sh

# local dev startup
./scripts/start_local_stack.sh

# check status
python scripts/infra_status.py --env-file .env --json

# Terraform direct
cd infra
terraform init
terraform validate
terraform plan
terraform apply
```

## Final note

This operational layer is designed to keep the repo safe, reproducible, and easy to bootstrap without relying on fragile one-off manual steps. The intent is to let local development, CI validation, and production infrastructure checks all follow the same guardrails.
