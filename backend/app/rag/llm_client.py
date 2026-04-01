"""
llm_client.py — Shared LLM client factory functions.

Provides _get_llm_client() and _get_model_name() as a single source of truth
for LLM client construction. Imported by both agent.py and document_analyzer.py
to avoid a circular dependency.
"""
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.config import settings


def _get_llm_client() -> AsyncOpenAI | AsyncAzureOpenAI:
    """Return the correct async LLM client based on APP_ENV.

    Returns:
        AsyncAzureOpenAI when APP_ENV=production (data stays in Azure tenant).
        AsyncOpenAI otherwise (demo/development — direct OpenAI API).
    """
    if settings.app_env == "production":
        # ============================================================
        # PRODUCTION: Azure OpenAI
        # AWS equivalent: Amazon Bedrock
        # Set APP_ENV=production in .env to activate
        # ============================================================
        return AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    # ============================================================
    # DEMO: Plain OpenAI API
    # Switch to production: set APP_ENV=production in .env
    # ============================================================
    return AsyncOpenAI(api_key=settings.openai_api_key)


def _get_model_name() -> str:
    """Return the deployment/model name for the active environment.

    Returns:
        Azure deployment name in production, 'gpt-4o' in demo.
    """
    if settings.app_env == "production":
        return settings.azure_openai_deployment_name
    return "gpt-4o"
