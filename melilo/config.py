"""Env-driven settings.

The R2 layout has three buckets, all on the same R2 account:

- `R2_PUBLIC_BUCKET`   — public-facing archive (govparti-archive). Source for ingest.
- `R2_INTERNAL_BUCKET` — internal working bucket (govparti-internal). Also a source.
- `R2_MELILO_ENDPOINT` — destination bucket where OLMo-generated pairs land, and
                         where Melilo's own outputs will land later. Despite the
                         "ENDPOINT" suffix this is a bucket name, not a URL.

Public-bucket source URIs are written as `https://archive.govparti.org/<key>` so
civic readers can click through to the canonical document. Internal-bucket
sources stay as `r2://govparti-internal/<key>` since they have no public URL.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Logical bucket roles. The values match the `--bucket` CLI flag in the scripts.
BUCKET_PUBLIC = "public"
BUCKET_INTERNAL = "internal"
SOURCE_BUCKETS = (BUCKET_PUBLIC, BUCKET_INTERNAL)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- R2 credentials (shared across all three buckets) ---------------------
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_endpoint: str = Field(default="", alias="R2_ENDPOINT")

    # --- Buckets --------------------------------------------------------------
    r2_public_bucket: str = Field(default="govparti-archive", alias="R2_PUBLIC_BUCKET")
    r2_internal_bucket: str = Field(default="govparti-internal", alias="R2_INTERNAL_BUCKET")
    r2_public_base_url: str = Field(
        default="https://archive.govparti.org", alias="R2_PUBLIC_BASE_URL"
    )
    # The Melilo bucket where pair JSONL archives are written. The env var
    # R2_MELILO_ENDPOINT holds a *URL* (custom-domain / public base URL for the
    # bucket, if any) — it's not used for S3 writes, since writes go through
    # R2_ENDPOINT + this bucket name.
    r2_melilo_bucket: str = Field(default="melilo-pairs", alias="R2_MELILO_BUCKET")
    r2_melilo_base_url: str = Field(default="", alias="R2_MELILO_ENDPOINT")

    # --- Models ---------------------------------------------------------------
    translator_model: str = Field(
        default="allenai/Olmo-3-7B-Instruct", alias="TRANSLATOR_MODEL"
    )
    student_model: str = Field(
        default="allenai/OLMo-2-0425-1B-SFT", alias="STUDENT_MODEL"
    )
    prompt_version: str = Field(
        default="v4-plain-english-grade-5", alias="PROMPT_VERSION"
    )

    hf_token: str = Field(default="", alias="HF_TOKEN")

    # --- Neon (Postgres) for pair query layer --------------------------------
    # Belt-and-suspenders storage: every pair is written to R2 (archive) AND Neon
    # (query layer). SFT reads from Neon; the R2 JSONLs are the immutable backup.
    neon_database_url: str = Field(default="", alias="NEON_DATABASE_URL")

    # --- Translator backend --------------------------------------------------
    # `hf`       : load the HF transformers model in-process (default; slow on CPU,
    #              fine on a beefy GPU). Uses TRANSLATOR_MODEL above.
    # `openai`   : hit any OpenAI-compatible HTTP API. Works with local Ollama,
    #              Parasail, OpenRouter, vLLM-served endpoints, etc. Swap providers
    #              by changing OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL.
    backend: str = Field(default="openai", alias="MELILO_BACKEND")
    backend_concurrency: int = Field(default=2, alias="MELILO_BACKEND_CONCURRENCY")
    backend_max_tokens: int = Field(default=2048, alias="MELILO_BACKEND_MAX_TOKENS")
    backend_temperature: float = Field(default=0.0, alias="MELILO_BACKEND_TEMPERATURE")

    # OpenAI-compatible backend config. Defaults point at a local Ollama instance.
    openai_base_url: str = Field(
        default="http://localhost:11434/v1", alias="OPENAI_BASE_URL"
    )
    openai_api_key: str = Field(default="ollama", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="olmo-3:7b-instruct", alias="OPENAI_MODEL")

    # --- Helpers --------------------------------------------------------------
    def source_bucket_name(self, role: str) -> str:
        """Map a logical role (`public` / `internal`) to the configured bucket name."""
        if role == BUCKET_PUBLIC:
            return self.r2_public_bucket
        if role == BUCKET_INTERNAL:
            return self.r2_internal_bucket
        raise ValueError(f"unknown source bucket role: {role!r}; valid: {SOURCE_BUCKETS}")

    def source_uri(self, role: str, key: str) -> str:
        """Build the `source_uri` field stored in pair records. Public bucket docs
        get a clickable https URL so civic readers can reach the canonical source;
        internal docs stay as opaque r2:// URIs."""
        if role == BUCKET_PUBLIC:
            base = self.r2_public_base_url.rstrip("/")
            return f"{base}/{key}"
        if role == BUCKET_INTERNAL:
            return f"r2://{self.r2_internal_bucket}/{key}"
        raise ValueError(f"unknown source bucket role: {role!r}; valid: {SOURCE_BUCKETS}")


settings = Settings()
