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
    # Misleadingly named in .env — this is the bucket name where Melilo pairs go.
    r2_melilo_bucket: str = Field(default="", alias="R2_MELILO_ENDPOINT")

    # --- Models ---------------------------------------------------------------
    translator_model: str = Field(
        default="allenai/Olmo-3-7B-Instruct", alias="TRANSLATOR_MODEL"
    )
    student_model: str = Field(
        default="allenai/OLMo-2-0425-1B-SFT", alias="STUDENT_MODEL"
    )
    prompt_version: str = Field(
        default="v3-pirac-brief-summary-walkthrough", alias="PROMPT_VERSION"
    )

    hf_token: str = Field(default="", alias="HF_TOKEN")

    # --- Neon (Postgres) for pair query layer --------------------------------
    # Belt-and-suspenders storage: every pair is written to R2 (archive) AND Neon
    # (query layer). SFT reads from Neon; the R2 JSONLs are the immutable backup.
    neon_database_url: str = Field(default="", alias="NEON_DATABASE_URL")

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
