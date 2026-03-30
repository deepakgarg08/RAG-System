"""
config.py — Single source of truth for all configuration values.
Reads from .env via pydantic-settings. This is the ONLY file in the project
that reads environment variables — all other modules import from here.
"""
import logging
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    # --- Application ---
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- OpenAI (DEMO mode) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # --- Vector store (DEMO) ---
    chroma_persist_path: str = Field(default="./chroma_db", alias="CHROMA_PERSIST_PATH")

    # --- File storage (DEMO) ---
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")
    registry_path: str = Field(default="./ingestion_registry.json", alias="REGISTRY_PATH")

    # --- ETL parameters ---
    max_chunk_size: int = Field(default=1000, alias="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    top_k_results: int = Field(default=8, alias="TOP_K_RESULTS")  # raised from 5 for better recall

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

    model_config = {"env_file": ".env", "populate_by_name": True}


# Singleton — all modules import this instance
settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
