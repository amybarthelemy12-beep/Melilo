# Melilo Script Commands Reference

Complete reference for every script in the repo, what it does, and how to run it.

## Quick command index

| Script | Command | Purpose |
|--------|---------|---------|
| setup_infra.sh | `./scripts/setup_infra.sh` | Bootstrap Terraform, validate credentials, provision R2 buckets |
| validate_env.py | `python scripts/validate_env.py --env-file .env` | Validate all required environment variables |
| start_local_stack.sh | `./scripts/start_local_stack.sh` | Prepare local dev environment, verify Ollama model |
| infra_status.py | `python scripts/infra_status.py --env-file .env --json` | Check R2 bucket health and deployment metadata |

---

## 1. `./scripts/setup_infra.sh`

**What it does:**
Automates the entire infrastructure bootstrap process for Cloudflare R2, Terraform state initialization, and environment configuration.

**When to use:**
- First-time infrastructure setup
- Re-provisioning buckets
- Refreshing infrastructure after account or region changes
- Recovering from a corrupted state

**Command:**
```bash
./scripts/setup_infra.sh
```

**With environment overrides:**
```bash
TF_VAR_deployment_environment=prod \
TF_VAR_source_bucket_name=melilo-legal-source-prod \
TF_VAR_pairs_bucket_name=melilo-pairs-prod \
./scripts/setup_infra.sh
```

**What happens step-by-step:**

1. Verifies `terraform` and `python3` are installed
2. Loads existing `.env` file (if present) to check for credentials
3. Validates `CLOUDFLARE_API_TOKEN` is set
4. Validates `TF_VAR_cloudflare_account_id` is set
5. Copies `.env.example` to `.env` (if `.env` doesn't exist)
6. Populates required variables from environment into `.env`
7. Changes to `infra/` directory
8. Runs `terraform init -upgrade`
9. Runs `terraform validate`
10. Runs `terraform apply -auto-approve`
11. Saves Terraform outputs to `.terraform-output.json`
12. Runs `python scripts/validate_env.py --strict` to verify final state
13. Updates `.env` with generated bucket names and R2 endpoint from Terraform outputs
14. Performs optional Neon database connectivity check
15. Prints next-step commands

**Expected output:**
```
[setup_infra] Terraform setup complete.
[setup_infra] Next run: python scripts/validate_env.py --env-file .env
[setup_infra] Next run: ./scripts/start_local_stack.sh
```

**If it fails:**
- Missing `CLOUDFLARE_API_TOKEN` → export it: `export CLOUDFLARE_API_TOKEN=...`
- Missing `TF_VAR_cloudflare_account_id` → export it: `export TF_VAR_cloudflare_account_id=...`
- Terraform validation error → check `infra/variables.tf` and `infra/main.tf`
- `.env` validation fails → review error message and fill in missing values manually

**Environment variables used:**
- `CLOUDFLARE_API_TOKEN` (required)
- `TF_VAR_cloudflare_account_id` (required)
- `TF_VAR_deployment_environment` (optional, default: `dev`)
- `TF_VAR_source_bucket_name` (optional)
- `TF_VAR_pairs_bucket_name` (optional)
- `NEON_DATABASE_URL` (optional, used for connectivity check)
- `ENV_FILE` (optional, default: `.env`)

---

## 2. `python scripts/validate_env.py`

**What it does:**
Checks that all required environment variables are present and correct before running infrastructure or data jobs.

**When to use:**
- Before running Terraform
- Before running backfill or model jobs
- In CI/CD to gate deployments
- Before local model inference
- As a sanity check before any external API call

**Basic command:**
```bash
python scripts/validate_env.py --env-file .env
```

**Strict mode (checks production-readiness):**
```bash
python scripts/validate_env.py --env-file .env --strict
```

**What it checks:**

Basic mode validates:
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
- `OPENAI_MODEL`
- `TRANSLATOR_MODEL`

Strict mode adds:
- `TF_VAR_deployment_environment`
- `TF_VAR_source_bucket_name`
- `TF_VAR_pairs_bucket_name`
- `R2_MELILO_ENDPOINT`

**Expected output (pass):**
```
[validate_env] Environment validation passed.
```
Exit code: `0`

**Expected output (fail):**
```
[validate_env] ERROR: Missing required environment variables:
- CLOUDFLARE_API_TOKEN (Cloudflare token with R2 access.)
- R2_ACCESS_KEY_ID (R2 access key ID.)
```
Exit code: `1`

**How it reads variables:**
1. First checks OS environment (`$CLOUDFLARE_API_TOKEN`, etc.)
2. Falls back to `.env` file if not in OS
3. Trims quotes and whitespace

**If it fails:**
- Fill in missing values in `.env`
- Or export them in the shell: `export CLOUDFLARE_API_TOKEN=...`
- Rerun validation

---

## 3. `./scripts/start_local_stack.sh`

**What it does:**
Prepares the local development environment, verifies Ollama installation, and ensures the required model is available for local inference.

**When to use:**
- Starting local development
- Before running inference on a local machine
- After installing Ollama for the first time
- To verify the model is ready

**Command:**
```bash
./scripts/start_local_stack.sh
```

**What it does step-by-step:**

1. Checks if `.env` exists; creates default if missing
2. Reads `OPENAI_MODEL` or `TRANSLATOR_MODEL` from `.env`
3. Checks if Ollama is installed
4. If Ollama is installed:
   - Runs `ollama list --format json`
   - Checks if the required model is already available
   - If model is missing, runs `ollama pull <model-name>`
5. Prints next-step suggestions

**Expected output (model available):**
```
[start_local_stack] Ollama model olmo-3:7b-instruct is available.
[start_local_stack] Local stack defaults ready.
[start_local_stack] Suggested next steps:
  1. python scripts/validate_env.py --env-file .env
  2. python scripts/infra_status.py --env-file .env --json
  3. melilo-backfill --prefix ...
```

**Expected output (model needs pull):**
```
[start_local_stack] Pulling Ollama model: olmo-3:7b-instruct
pulling manifest
...
[start_local_stack] Local stack defaults ready.
```

**Expected output (Ollama not installed):**
```
[start_local_stack] Ollama is not installed. Skipping model pull.
[start_local_stack] Local stack defaults ready.
```

**What `.env` defaults are created:**

```dotenv
CLOUDFLARE_API_TOKEN=
TF_VAR_cloudflare_account_id=
TF_VAR_deployment_environment=dev
TF_VAR_source_bucket_name=melilo-legal-source-dev
TF_VAR_pairs_bucket_name=melilo-pairs-dev
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_ENDPOINT=
R2_PUBLIC_BUCKET=govparti-archive
R2_INTERNAL_BUCKET=govparti-internal
R2_MELILO_BUCKET=melilo-pairs
R2_MELILO_ENDPOINT=
NEON_DATABASE_URL=
MELILO_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=olmo-3:7b-instruct
TRANSLATOR_MODEL=allenai/OLMo-3-7B-Instruct
```

**If it fails:**
- Ollama not found → Install Ollama: https://ollama.ai
- Model pull times out → Check internet connectivity
- Model already pulled but not recognized → Restart Ollama service

**Environment variables used:**
- `ENV_FILE` (optional, default: `.env`)
- `OPENAI_MODEL` (optional, read from `.env`)
- `TRANSLATOR_MODEL` (optional, read from `.env`)

---

## 4. `python scripts/infra_status.py`

**What it does:**
Checks the health of your R2 buckets, verifies deployment metadata, and provides operational status information.

**When to use:**
- Daily operational checks
- Deployment verification
- Troubleshooting R2 connectivity issues
- Monitoring bucket existence and state
- Before and after infrastructure changes

**Basic command:**
```bash
python scripts/infra_status.py --env-file .env
```

**JSON output (for parsing or monitoring):**
```bash
python scripts/infra_status.py --env-file .env --json
```

**What it checks:**

1. Reads `.env` for Cloudflare token and account ID
2. Queries Cloudflare R2 API for bucket list
3. Verifies the configured bucket name exists
4. Reads `infra/manifest.json` for deployment metadata
5. Reports versioning status
6. Outputs status as CLI or JSON

**Expected CLI output:**
```
Bucket existence: True
Versioning status: True
Deployment metadata: {'infrastructure_version': '2026.10.09', 'deployment_environment': 'dev', ...}
```
Exit code: `0`

**Expected JSON output:**
```json
{
  "bucket": "melilo-pairs-dev",
  "account_id": "abc123def456",
  "checks": {
    "bucket_exists": true,
    "versioning_status_ok": true
  },
  "cloudflare": {
    "result": [
      {
        "name": "melilo-pairs-dev",
        "created": "2026-10-09T00:00:00Z"
      }
    ],
    "success": true
  },
  "manifest": {
    "infrastructure_version": "2026.10.09",
    "deployment_environment": "dev",
    "versioning_enabled": true
  }
}
```
Exit code: `0`

**If bucket_exists is False:**
```json
{
  "bucket": "melilo-pairs-dev",
  "checks": {
    "bucket_exists": false,
    "versioning_status_ok": false
  }
}
```
Exit code: `1`

**If it fails:**
- Missing `CLOUDFLARE_API_TOKEN` → Set environment variable or in `.env`
- Missing `TF_VAR_cloudflare_account_id` → Set in environment or `.env`
- Bucket not found → Verify bucket name matches `TF_VAR_pairs_bucket_name`
- Cloudflare API error → Check token permissions, ensure it has R2 access

**Environment variables used:**
- `CLOUDFLARE_API_TOKEN` (required)
- `TF_VAR_cloudflare_account_id` (required)
- `R2_MELILO_BUCKET` (required, default: `melilo-pairs`)

---

## Integrated workflow examples

### Fresh setup from scratch

```bash
# 1. Prepare environment
cp .env.example .env
# (edit .env with your Cloudflare token and account ID)

# 2. Validate environment
python scripts/validate_env.py --env-file .env

# 3. Bootstrap infrastructure
./scripts/setup_infra.sh

# 4. Prepare local runtime
./scripts/start_local_stack.sh

# 5. Check status
python scripts/infra_status.py --env-file .env --json
```

### Daily operational check

```bash
# Validate nothing broke
python scripts/validate_env.py --env-file .env

# Check R2 and deployment health
python scripts/infra_status.py --env-file .env --json
```

### Before running a backfill job

```bash
# Ensure everything is ready
python scripts/validate_env.py --env-file .env --strict

# Verify infrastructure is healthy
python scripts/infra_status.py --env-file .env

# Ensure local Ollama model is available
./scripts/start_local_stack.sh

# Now safe to run
melilo-backfill --prefix federal/caselaw/ --task summary --source-type case --license PD --source-org CourtListener
```

### Troubleshooting infrastructure

```bash
# Check which vars are missing
python scripts/validate_env.py --env-file .env --strict

# Inspect R2 status in detail
python scripts/infra_status.py --env-file .env --json | python -m json.tool

# Re-run infrastructure bootstrap
./scripts/setup_infra.sh

# Verify post-bootstrap
python scripts/validate_env.py --env-file .env --strict
python scripts/infra_status.py --env-file .env --json
```

---

## Exit codes and error handling

All scripts follow standard Unix conventions:

- Exit code `0` → success
- Exit code `1` → recoverable error (missing config, validation failed)
- Exit code `2` → command-line argument error

**Typical error responses:**

```bash
# Missing required variable
$ python scripts/validate_env.py --env-file .env
[validate_env] ERROR: Missing required environment variables:
- CLOUDFLARE_API_TOKEN (...)
$ echo $?
1

# Success
$ python scripts/validate_env.py --env-file .env
[validate_env] Environment validation passed.
$ echo $?
0

# Bucket not found
$ python scripts/infra_status.py --env-file .env
$ echo $?
1
```

---

## Cheat sheet

```bash
# Validate everything
python scripts/validate_env.py --env-file .env --strict

# Full bootstrap
./scripts/setup_infra.sh

# Local setup
./scripts/start_local_stack.sh

# Check health
python scripts/infra_status.py --env-file .env --json

# All at once (fresh machine)
cp .env.example .env && \
  python scripts/validate_env.py --env-file .env && \
  ./scripts/setup_infra.sh && \
  ./scripts/start_local_stack.sh && \
  python scripts/infra_status.py --env-file .env --json

# Periodic operational check
python scripts/validate_env.py --env-file .env && python scripts/infra_status.py --env-file .env --json
```

---

## Additional notes

- All scripts are idempotent where possible (safe to re-run)
- All scripts accept environment variables and `.env` file inputs
- All scripts provide clear error messages on failure
- Scripts follow the principle of failing fast on validation errors
- No script modifies production data without explicit user action
