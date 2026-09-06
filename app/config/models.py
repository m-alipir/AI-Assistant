"""Configuration loader for model-role mappings; business services never select model slugs."""

from pathlib import Path

import yaml

from app.llm.core import ModelSettings


def load_model_settings(path: Path) -> ModelSettings:
    """Load role mappings, fallbacks, and budget limits from safe YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("model configuration root must be a mapping")
    return ModelSettings.model_validate(data)
