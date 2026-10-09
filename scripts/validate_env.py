#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "CLOUDFLARE_API_TOKEN": "Cloudflare token with R2 access.",
    "TF_VAR_cloudflare_account_id": "Cloudflare account ID used by Terraform.",
    "R2_ACCESS_KEY_ID": "R2 access key ID.",
    "R2_SECRET_ACCESS_KEY": "R2 secret access key.",
    "R2_ENDPOINT": "Cloudflare R2 endpoint URL.",
    "R2_PUBLIC_BUCKET": "Public archive bucket name.",
    "R2_INTERNAL_BUCKET": "Internal source bucket name.",
    "R2_MELILO_BUCKET": "Melilo output bucket name.",
    "NEON_DATABASE_URL": "Neon PostgreSQL connection URL.",
    "MELILO_BACKEND": "Translator backend: openai or hf.",
    "OPENAI_BASE_URL": "OpenAI-compatible API base URL.",
    "OPENAI_MODEL": "OpenAI-compatible model identifier.",
    "TRANSLATOR_MODEL": "Translation model identifier.",
}


def load_env_file(path: Path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_value(key, env, env_file_values):
    if key in env and env[key]:
        return env[key]
    if key in env_file_values and env_file_values[key]:
        return env_file_values[key]
    return ""


def validate(required, env, env_file_values):
    missing = []
    for key, description in required.items():
        value = get_value(key, env, env_file_values)
        if not value:
            missing.append(f"{key} ({description})")
    if missing:
        raise ValueError("Missing required environment variables:\n- " + "\n- ".join(missing))


def main():
    parser = argparse.ArgumentParser(description="Validate environment configuration for Melilo infrastructure.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to the env file to validate.")
    parser.add_argument("--strict", action="store_true", help="Require a full production-style validation set.")
    args = parser.parse_args()

    env = dict(os.environ)
    env_file_values = load_env_file(args.env_file)

    try:
        validate(REQUIRED_KEYS, env, env_file_values)
    except ValueError as exc:
        print(f"[validate_env] ERROR: {exc}", file=sys.stderr)
        return 1

    if args.strict:
        strict_keys = {
            "TF_VAR_deployment_environment": "Deployment environment label.",
            "TF_VAR_source_bucket_name": "Source bucket name for Terraform.",
            "TF_VAR_pairs_bucket_name": "Pairs bucket name for Terraform.",
            "R2_MELILO_ENDPOINT": "Public endpoint for the Melilo bucket.",
        }
        try:
            validate(strict_keys, env, env_file_values)
        except ValueError as exc:
            print(f"[validate_env] ERROR: {exc}", file=sys.stderr)
            return 1

    print("[validate_env] Environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
