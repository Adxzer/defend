import pytest

from defend_api.config import DefendConfig, ProviderConfig, ThresholdsConfig, get_defend_config


@pytest.mark.unit
def test_defend_config_validation_threshold_order():
    with pytest.raises(ValueError):
        DefendConfig(
            provider=ProviderConfig(primary="defend"),
            thresholds=ThresholdsConfig(block=0.3, flag=0.5),
        )


@pytest.mark.unit
def test_get_defend_config_errors_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="defend.config.yaml not found"):
        get_defend_config.cache_clear()  # type: ignore[attr-defined]
        get_defend_config()


@pytest.mark.unit
def test_get_defend_config_loads_valid_file(tmp_path, monkeypatch):
    cfg = """
provider:
  primary: defend
api_keys: {}
thresholds:
  block: 0.7
  flag: 0.3
guards:
  input:
    provider: defend
    modules: []
  output:
    provider: claude
    modules: []
    on_fail: block
  session_ttl_seconds: 300
"""
    (tmp_path / "defend.config.yaml").write_text(cfg, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    get_defend_config.cache_clear()  # type: ignore[attr-defined]
    config = get_defend_config()
    assert config.provider.primary.value == "defend"
    assert config.thresholds.block == 0.7
    assert config.thresholds.flag == 0.3

