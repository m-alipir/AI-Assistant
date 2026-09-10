from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "evals" / "promptfoo" / "promptfooconfig.yaml"


def test_promptfoo_config_is_sanitized_manual_and_token_bounded() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["sharing"] is False
    provider = config["providers"][0]
    assert provider["id"] == "openai:chat:{{ env.PROMPTFOO_MODEL_ID }}"
    assert provider["config"]["apiKeyEnvar"] == "PROMPTFOO_OPENROUTER_API_KEY"
    assert provider["config"]["max_tokens"] == 300
    assert provider["config"]["requestsPerMinute"] == 1
    assert len(config["tests"]) == 5
    serialized = CONFIG_PATH.read_text(encoding="utf-8").casefold()
    forbidden = ("gmail", "javascript", "file://", "redteam")
    assert not any(marker in serialized for marker in forbidden)


def test_promptfoo_config_keeps_untrusted_source_delimiters() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    prompt = config["prompts"][0]
    assert "<source>" in prompt and "</source>" in prompt
    assert "untrusted source data" in prompt
    source_texts = [case["vars"]["source_text"] for case in config["tests"]]
    assert any("IGNORE PRIOR INSTRUCTIONS" in source_text for source_text in source_texts)
