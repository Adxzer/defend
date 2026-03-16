import pytest

from defend_api.modules import build_modules_from_specs, get_active_modules
from defend_api.providers.base import ProviderUnavailableError
from defend_api.routers.guard import guard_output
from defend_api.schemas import GuardAction, GuardOutputRequest, ProviderName


@pytest.mark.asyncio
async def test_output_modules_are_discoverable():
    active = get_active_modules()
    assert "prompt_leak" in active
    assert "pii_output" in active


def test_build_modules_from_specs_with_kwargs():
    modules = build_modules_from_specs([{"topic_output": {"allowed_topics": ["billing"]}}])
    assert len(modules) == 1
    assert modules[0].name == "topic_output"
    assert '"billing"' in modules[0].system_prompt()


@pytest.mark.asyncio
async def test_guard_output_on_fail_retry_suggested(monkeypatch):
    # Patch config to force retry_suggested on provider failure.
    from defend_api import config as config_mod

    real = config_mod.get_defend_config()
    patched = real.model_copy(deep=True)
    patched.guards.output.on_fail = GuardAction.RETRY_SUGGESTED
    patched.guards.output.provider = ProviderName.CLAUDE
    patched.guards.output.modules = ["prompt_leak"]

    monkeypatch.setattr(config_mod, "get_defend_config", lambda: patched)

    class FailingProvider:
        supports_modules = True
        name = ProviderName.CLAUDE

        async def evaluate(self, text, session_id=None, modules=None):
            raise ProviderUnavailableError("boom")

    import defend_api.routers.guard as guard_router

    monkeypatch.setattr(guard_router, "get_defend_config", lambda: patched)
    monkeypatch.setattr(guard_router, "get_provider", lambda name: FailingProvider())

    res = await guard_output(GuardOutputRequest(text="hello", session_id=None))
    payload = res.body.decode("utf-8")
    assert '"action":"retry_suggested"' in payload

