from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_source_bucket: str = Field(default="melilo-legal-source", alias="R2_SOURCE_BUCKET")
    r2_pairs_bucket: str = Field(default="melilo-pairs", alias="R2_PAIRS_BUCKET")

    translator_model: str = Field(
        default="allenai/Olmo-3-7B-Instruct", alias="TRANSLATOR_MODEL"
    )
    student_model: str = Field(default="allenai/OLMo-2-0425-1B", alias="STUDENT_MODEL")
    prompt_version: str = Field(default="v1", alias="PROMPT_VERSION")

    hf_token: str = Field(default="", alias="HF_TOKEN")

    @property
    def r2_endpoint(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


settings = Settings()
