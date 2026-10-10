import pytest

from aftermath_api.config import SECRET_RE, format_status, load_settings


def test_process_env_wins(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("AFTERMATH_ENV=dev\nDATABASE_URL=from-file\nT2_LLM_API_KEY=\n", encoding="utf-8")
    settings = load_settings(envf, {"DATABASE_URL": "from-process", "AFTERMATH_ENV": "dev"})
    assert settings.database_url == "from-process"
    assert settings.decisions == "abstain_only"
    assert settings.llm_configured is False


def test_llm_alias_copied_when_t2_empty(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("LLM_API_KEY=k\nLLM_BASE_URL=https://example.test/v1\nLLM_MODEL=m\n", encoding="utf-8")
    settings = load_settings(envf, {})
    assert settings.llm_configured is True
    assert settings.decisions == "model"


def test_missing_database_exits_in_prod(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("AFTERMATH_ENV=prod\n", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        load_settings(envf, {"AFTERMATH_ENV": "prod"})
    assert caught.value.code == 2


def test_missing_llm_does_not_exit(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("AFTERMATH_ENV=prod\nDATABASE_URL=postgres\n", encoding="utf-8")
    settings = load_settings(envf, {"AFTERMATH_ENV": "prod", "DATABASE_URL": "postgres"})
    assert settings.decisions == "abstain_only"


def test_status_has_no_secret_pattern(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("AFTERMATH_API_TOKEN=secret-value\nDATABASE_URL=postgresql://user:pw@host/db\n", encoding="utf-8")
    text = format_status(load_settings(envf, {}))
    assert "secret-value" not in text
    assert "postgresql://" not in text
    assert SECRET_RE.search(text) is None
    assert "SET" in text


def test_listen_port_uses_render_port(monkeypatch):
    from aftermath_api.__main__ import listen_port

    monkeypatch.setenv("PORT", "10000")
    assert listen_port() == 10000


def test_malformed_lines_ignored(tmp_path):
    envf = tmp_path / ".env"
    envf.write_text("# comment\nNOT_A_PAIR\nAFTERMATH_ENV=test\n", encoding="utf-8")
    assert load_settings(envf, {}).env == "test"
