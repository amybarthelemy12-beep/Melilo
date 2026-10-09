#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ENV_PATH = Path(".env")
DEFAULT_MODEL = "allenai/OLMo-3-7B-Instruct"


def env_value(key: str, env: dict, env_file: Path) -> str:
    if key in env and env.get(key):
        return env[key]
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return ""


def ensure_file(path: Path, contents: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(contents, encoding="utf-8")


def ensure_ollama_model(model_name: str):
    if shutil.which("ollama") is None:
        print("[start_local_stack] Ollama is not installed. Skipping model pull.")
        return
    cmd = ["ollama", "list", "--format", "json"]
    try:
        comp = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if comp.returncode != 0:
            print("[start_local_stack] ollama list failed; model verification may be skipped.")
            return
        try:
            payload = json.loads(comp.stdout or "[]")
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, list) and any(item.get("name") == model_name for item in payload):
            print(f"[start_local_stack] Ollama model {model_name} is available.")
            return
        print(f"[start_local_stack] Pulling Ollama model: {model_name}")
        subprocess.run(["ollama", "pull", model_name], check=True)
    except Exception as exc:
        print(f"[start_local_stack] Warning: unable to verify Ollama model: {exc}")


def main():
    env_file = Path(os.environ.get("ENV_FILE", ".env"))
    env = dict(os.environ)

    if not env_file.exists():
        ensure_file(
            env_file,
            """# Local defaults for Melilo development
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
""",
        )

    model_name = env_value("OPENAI_MODEL", env, env_file) or env_value("TRANSLATOR_MODEL", env, env_file) or "olmo-3:7b-instruct"
    if "allenai" in model_name and ":" not in model_name:
        model_name = model_name.lower().replace("allenai/", "")
    ensure_ollama_model(model_name)

    print("[start_local_stack] Local stack defaults ready.")
    print("[start_local_stack] Suggested next steps:")
    print("  1. python scripts/validate_env.py --env-file .env")
    print("  2. python scripts/infra_status.py --env-file .env --json")
    print("  3. melilo-backfill --prefix ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
