#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request


def load_env(path: Path):
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


def env_value(env, key, default=""):
    if key in env and env[key]:
        return env[key]
    return default


def fetch_cloudflare_buckets(account_id: str, token: str):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets"
    req = request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload


def main():
    parser = argparse.ArgumentParser(description="Check infrastructure health for Melilo R2 and deployment metadata.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="Path to .env file.")
    parser.add_argument("--json", action="store_true", help="Emit results as JSON.")
    args = parser.parse_args()

    env = load_env(args.env_file)
    token = env_value(env, "CLOUDFLARE_API_TOKEN")
    account_id = env_value(env, "TF_VAR_cloudflare_account_id") or env_value(env, "CLOUDFLARE_ACCOUNT_ID")
    bucket_name = env_value(env, "R2_MELILO_BUCKET", "melilo-pairs")

    status = {
        "bucket": bucket_name,
        "account_id": account_id,
        "versioning_enabled": bool(env_value(env, "TF_VAR_versioning_enabled", "true").lower() == "true"),
        "manifest": {},
        "cloudflare": None,
        "checks": {
            "bucket_exists": False,
            "versioning_status_ok": False,
        },
    }

    manifest_path = Path("infra/manifest.json")
    if manifest_path.exists():
        status["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))

    if token and account_id:
        try:
            payload = fetch_cloudflare_buckets(account_id, token)
            status["cloudflare"] = payload
            result = payload.get("result", []) if isinstance(payload, dict) else []
            names = {item.get("name") for item in result if isinstance(item, dict) and item.get("name")}
            status["checks"]["bucket_exists"] = bucket_name in names
            status["checks"]["versioning_status_ok"] = bool(status["checks"]["bucket_exists"]) or bool(status["manifest"].get("versioning_enabled", True))
        except Exception as exc:
            status["cloudflare_error"] = str(exc)

    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(f"Bucket existence: {status['checks']['bucket_exists']}")
        print(f"Versioning status: {status['checks']['versioning_status_ok']}")
        print(f"Deployment metadata: {status['manifest']}")

    if not status["checks"]["bucket_exists"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
