"""Advisory OpenRouter catalog command; it never rewrites configuration."""

import argparse
import asyncio
import os
from pathlib import Path

from app.config.models import load_model_settings
from app.llm.core import OpenRouterClient, advisory_candidates


async def main() -> None:
    """Print eligible model IDs from the provider catalog using an explicit environment key."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--structured", action="store_true")
    parser.add_argument("--config", type=Path, default=Path("config/models.example.yaml"))
    arguments = parser.parse_args()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required for an advisory catalog query")
    settings = load_model_settings(arguments.config)
    catalog = await OpenRouterClient(api_key, settings.openrouter.base_url).list_models()
    print("\n".join(advisory_candidates(catalog, arguments.structured)))


if __name__ == "__main__":
    asyncio.run(main())
