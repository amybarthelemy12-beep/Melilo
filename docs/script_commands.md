# Melilo Script Commands Reference

A practical command guide for all script-driven setup and validation tasks in this repo.

## Setup and validation

### 1) Initialize infrastructure
```bash
./scripts/setup_infra.sh
```
Runs Terraform bootstrap, validates the Cloudflare token/account, creates or updates the configured buckets, writes Terraform output values into `.env`, and then verifies the final environment.

### 2) Validate environment variables
```bash
python scripts/validate_env.py --env-file .env
```
Checks for required config such as Cloudflare token/account ID, R2 values, Neon URL, model settings, and backend settings.

### 3) Strict validation for deployment readiness
```bash
python scripts/validate_env.py --env-file .env --strict
```
Performs the fuller production-style check for bucket names, environment values, and required deployment metadata.

## Local runtime

### 4) Launch local dev / Ollama stack
```bash
./scripts/start_local_stack.sh
```
Checks whether Ollama is installed, ensures the configured model is present, and prints next steps for local use.

### 5) Health check on infrastructure
```bash
python scripts/infra_status.py --env-file .env --json
```
Checks if the configured R2 bucket exists, reads manifest metadata, and emits a JSON status payload for quick troubleshooting.

## Terraform

### 6) Standard Terraform workflow
```bash
cd infra
terraform init
terraform validate
terraform plan
terraform apply
```
Applies the Cloudflare R2 infrastructure and exposes output values for scripts and `.env` population.

## Existing repo scripts

### 7) Backfill pipeline
```bash
python scripts/backfill.py
```
Runs backfill processing tasks for the data pipeline.

### 8) Ingest pipeline
```bash
python scripts/ingest.py
```
Handles raw ingest tasks.

### 9) Training pipeline
```bash
python scripts/train.py
```
Runs training entry points for the repo.

### 10) Translation / model pipeline
```bash
python scripts/translate.py
```
Executes translation or model translation tasks.

### 11) Migration/bootstrap
```bash
python scripts/migrate.py
```
Used for database or migration bootstrapping work.

## Recommended command order

```bash
cp .env.example .env
python scripts/validate_env.py --env-file .env --strict
./scripts/setup_infra.sh
./scripts/start_local_stack.sh
python scripts/infra_status.py --env-file .env --json
```

## Troubleshooting shortcuts

```bash
# If validation fails
python scripts/validate_env.py --env-file .env --strict

# If infra is not healthy
python scripts/infra_status.py --env-file .env --json

# If the stack needs to be rebuilt
./scripts/setup_infra.sh
```

## Summary

These commands form the repo's local workflow for:
- environment validation
- Terraform infrastructure setup
- local runtime startup
- infra health checks
- operational sanity before external runs
