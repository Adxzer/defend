import pytest

from defend_api.modules import build_modules_from_specs, parse_module_spec
from defend_api.modules import get_active_modules


@pytest.mark.unit
def test_parse_module_spec_string():
    name, cfg = parse_module_spec("injection")
    assert name == "injection"
    assert cfg == {}


@pytest.mark.unit
def test_parse_module_spec_with_kwargs():
    spec = {"topic": {"allowed_topics": ["billing", "support"]}}
    name, cfg = parse_module_spec(spec)
    assert name == "topic"
    assert cfg == {"allowed_topics": ["billing", "support"]}


@pytest.mark.unit
def test_build_modules_from_specs_creates_expected_modules():
    specs = [
        "injection",
        {"pii": {}},
        {"topic": {"allowed_topics": ["billing"]}},
    ]
    modules = build_modules_from_specs(specs)
    names = {m.name for m in modules}
    assert "injection" in names
    assert "pii" in names
    assert "topic" in names


@pytest.mark.unit
def test_topic_module_system_prompt_includes_allowed_topics():
    # Use active modules registry to locate topic module implementation.
    active = get_active_modules()
    topic_cls = active.get("topic")
    assert topic_cls is not None
    topic = topic_cls(allowed_topics=["billing"])
    prompt = topic.system_prompt()
    assert "billing" in prompt

