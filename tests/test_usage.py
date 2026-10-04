import sqlite3
from pathlib import Path

import pytest

from axioms.audit_log import bind_request_id, reset_request_id
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


def test_usage_store_links_recorded_metadata_to_the_safe_request_correlation_id(tmp_path: Path) -> None:
    path = tmp_path / "usage.sqlite3"
    store = UsageStore(path)
    token = bind_request_id("provider-run_2026")
    try:
        store.record(provider="anthropic", model="test-model", input_tokens=8, output_tokens=4)
    finally:
        reset_request_id(token)

    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT request_id FROM llm_usage_events").fetchone()
    assert row == ("provider-run_2026",)


def test_usage_store_migrates_existing_usage_table_without_losing_prior_rows(tmp_path: Path) -> None:
    path = tmp_path / "legacy-usage.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE llm_usage_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO llm_usage_events
            (recorded_at, provider, model, input_tokens, output_tokens)
            VALUES ('2026-01-01T00:00:00+00:00', 'anthropic', 'legacy-model', 2, 1)
            """
        )

    store = UsageStore(path)
    assert store.summary()["request_count"] == 1
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(llm_usage_events)")}
        row = connection.execute("SELECT request_id FROM llm_usage_events").fetchone()
    assert "request_id" in columns
    assert row == (None,)
