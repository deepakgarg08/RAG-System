"""
config.py — Single source of truth for all configuration values.
"""

import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    # --- Application ---
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- HuggingFace ---
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")

    # --- OpenAI (DEMO mode) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # --- Vector store (DEMO) ---
    chroma_persist_path: str = Field(default="./chroma_db", alias="CHROMA_PERSIST_PATH")

    # --- File storage (DEMO) ---
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")
    registry_path: str = Field(default="./ingestion_registry.json", alias="REGISTRY_PATH")

    # --- ETL parameters ---
    max_chunk_size: int = Field(default=1500, alias="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    top_k_results: int = Field(default=8, alias="TOP_K_RESULTS")

    # --- Azure OpenAI (PRODUCTION — optional) ---
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(default="2024-02-01", alias="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_name: str = Field(default="gpt-4o", alias="AZURE_OPENAI_DEPLOYMENT_NAME")

    # --- Azure AI Search (PRODUCTION — optional) ---
    azure_search_endpoint: str = Field(default="", alias="AZURE_SEARCH_ENDPOINT")
    azure_search_key: str = Field(default="", alias="AZURE_SEARCH_KEY")
    azure_search_index_name: str = Field(default="riverty-contracts", alias="AZURE_SEARCH_INDEX_NAME")

    # --- Azure Blob Storage (PRODUCTION — optional) ---
    azure_storage_connection_string: str = Field(default="", alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_storage_container_name: str = Field(default="contracts", alias="AZURE_STORAGE_CONTAINER_NAME")

    # --- Azure Document Intelligence (PRODUCTION — optional) ---
    azure_doc_intelligence_endpoint: str = Field(default="", alias="AZURE_DOC_INTELLIGENCE_ENDPOINT")
    azure_doc_intelligence_key: str = Field(default="", alias="AZURE_DOC_INTELLIGENCE_KEY")

    # --- External Compliance Storage API (optional) ---
    compliance_api_url: str = Field(default="", alias="COMPLIANCE_API_URL")

    model_config = {
        "env_file": ".env",
        "populate_by_name": True,
    }

    def ensure_paths_exist(self):
        """Create required directories and files if they don't exist."""

        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.chroma_persist_path).mkdir(parents=True, exist_ok=True)

        registry_file = Path(self.registry_path)
        if not registry_file.exists():
            registry_file.parent.mkdir(parents=True, exist_ok=True)
            registry_file.write_text("{}", encoding="utf-8")

        logging.info("✅ All required directories and files are ensured.")


# Singleton
settings = Settings()

# Ensure paths
settings.ensure_paths_exist()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)