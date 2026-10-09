#!/usr/bin/env bash
set -euo pipefail

export ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export INFRA_DIR="$ROOT_DIR/infra"
export ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "[setup_infra] Terraform is not installed or not on PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[setup_infra] python3 is required." >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "[setup_infra] CLOUDFLARE_API_TOKEN is required." >&2
  exit 1
fi

if [[ -z "${TF_VAR_cloudflare_account_id:-}" ]]; then
  echo "[setup_infra] TF_VAR_cloudflare_account_id is required." >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/.env.example" ]]; then
  echo "[setup_infra] Missing .env.example template in repo root." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
fi

python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
env_file = Path(os.environ["ENV_FILE"])

required = {
    "CLOUDFLARE_API_TOKEN": os.environ.get("CLOUDFLARE_API_TOKEN", ""),
    "TF_VAR_cloudflare_account_id": os.environ.get("TF_VAR_cloudflare_account_id", ""),
    "TF_VAR_deployment_environment": os.environ.get("TF_VAR_deployment_environment", "dev"),
    "TF_VAR_source_bucket_name": os.environ.get("TF_VAR_source_bucket_name", "melilo-legal-source-dev"),
    "TF_VAR_pairs_bucket_name": os.environ.get("TF_VAR_pairs_bucket_name", "melilo-pairs-dev"),
    "R2_PUBLIC_BUCKET": os.environ.get("R2_PUBLIC_BUCKET", "govparti-archive"),
    "R2_INTERNAL_BUCKET": os.environ.get("R2_INTERNAL_BUCKET", "govparti-internal"),
    "R2_MELILO_BUCKET": os.environ.get("R2_MELILO_BUCKET", "melilo-pairs"),
    "NEON_DATABASE_URL": os.environ.get("NEON_DATABASE_URL", ""),
}

existing = {}
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()

for key, value in required.items():
    if value and key not in existing:
        with env_file.open("a", encoding="utf-8") as fh:
            if env_file.exists() and env_file.stat().st_size > 0 and not env_file.read_text(encoding="utf-8").endswith("\n"):
                fh.write("\n")
            fh.write(f"{key}={value}\n")
PY

cd "$INFRA_DIR"
terraform init -upgrade
terraform validate
terraform apply -auto-approve

terraform output -json > "$INFRA_DIR/.terraform-output.json"

python3 "$ROOT_DIR/scripts/validate_env.py" --env-file "$ENV_FILE" --strict || {
  echo "[setup_infra] Validation failed after apply. Check your environment values." >&2
  exit 1
}

python3 - "$ENV_FILE" "$INFRA_DIR/.terraform-output.json" <<'PY'
import json
import os
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
out_file = Path(sys.argv[2])

current = env_file.read_text(encoding="utf-8") if env_file.exists() else ""

if out_file.exists():
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    if "source_bucket_name" in payload:
        source = payload["source_bucket_name"]["value"]
        pairs = payload["pairs_bucket_name"]["value"]
        r2_endpoint = payload["r2_endpoint"]["value"]
        env_lines = [
            f"R2_PUBLIC_BUCKET={os.environ.get('R2_PUBLIC_BUCKET', 'govparti-archive')}",
            f"R2_INTERNAL_BUCKET={os.environ.get('R2_INTERNAL_BUCKET', 'govparti-internal')}",
            f"R2_MELILO_BUCKET={pairs}",
            f"R2_MELILO_ENDPOINT={r2_endpoint}",
            f"R2_ENDPOINT={r2_endpoint}",
            f"R2_SOURCE_BUCKET={source}",
            f"TF_VAR_source_bucket_name={source}",
            f"TF_VAR_pairs_bucket_name={pairs}",
        ]
        lines = current.splitlines()
        for item in env_lines:
            key, value = item.split("=", 1)
            replace = False
            for idx, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[idx] = f"{key}={value}"
                    replace = True
                    break
            if not replace:
                lines.append(f"{key}={value}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

if [[ -n "${NEON_DATABASE_URL:-}" ]]; then
  python3 - <<'PY'
import os
import socket
from urllib.parse import urlparse

url = os.environ.get("NEON_DATABASE_URL", "")
if not url:
    raise SystemExit(0)
parsed = urlparse(url)
if not parsed.hostname:
    raise SystemExit(1)
try:
    host = parsed.hostname
    port = parsed.port or 5432
    with socket.create_connection((host, port), timeout=5):
        pass
    print(f"[setup_infra] Neon connectivity check passed for {host}:{port}")
except Exception as exc:
    print(f"[setup_infra] Neon connectivity warning: {exc}")
PY
fi

echo "[setup_infra] Terraform setup complete."
echo "[setup_infra] Next run: python scripts/validate_env.py --env-file $ENV_FILE"
echo "[setup_infra] Next run: ./scripts/start_local_stack.sh"
