from pathlib import Path

import pytest

from axioms.usage import UsageStore, record_provider_usage


def test_usage_store_returns_content_free_aggregate_summary(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite3")
    store.record(provider="anthropic", model="test-model", input_tokens=12, output_tokens=7)
    store.record(provider="anthropic", model="test-model", input_tokens=3, output_tokens=5)
    store.record(provider="openai", model="other-model", input_tokens=9, output_tokens=2)

    assert store.summary() == {
        "request_count": 3,
        "input_tokens": 24,
        "output_tokens": 14,
        "by_provider": [
            {
                "provider": "anthropic",
                "model": "test-model",
                "request_count": 2,
                "input_tokens": 15,
                "output_tokens": 12,
            },
            {
                "provider": "openai",
                "model": "other-model",
                "request_count": 1,
                "input_tokens": 9,
                "output_tokens": 2,
            },
        ],
    }


def test_usage_store_rejects_negative_values_and_ignores_absent_usage(tmp_path: Path, monkeypatch) -> None:
    store = UsageStore(tmp_path / "usage.sqlite3")
    with pytest.raises(ValueError, match="non-negative"):
        store.record(provider="anthropic", model="test-model", input_tokens=-1, output_tokens=0)

    monkeypatch.setenv("AXIOMS_DATABASE_URL", f"sqlite:///{tmp_path / 'default.sqlite3'}")
    record_provider_usage(provider="anthropic", model="test-model", input_tokens=0, output_tokens=0)
    assert UsageStore().summary()["request_count"] == 0
