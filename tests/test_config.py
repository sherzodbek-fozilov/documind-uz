from documind.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DOCUMIND_LLM_API_KEY", "secret-value")
    monkeypatch.setenv("DOCUMIND_CHUNK_MAX_WORDS", "120")
    s = Settings(_env_file=None)
    assert s.chunk_max_words == 120
    # the key must never leak through repr/logging
    assert "secret-value" not in repr(s)
    assert s.llm_api_key.get_secret_value() == "secret-value"
