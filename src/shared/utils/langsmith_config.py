from langsmith import Client
from src.config.settings import get_settings
import os

def configure_langsmith():
    """Configure LangSmith tracing"""
    settings = get_settings()

    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_TRACING_V2"] = str(settings.langsmith_tracing_v2).lower()

    client = Client()
    return client

# Initialize on import
langsmith_client = configure_langsmith()
