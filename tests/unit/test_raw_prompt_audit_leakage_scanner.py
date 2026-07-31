import inspect

from services.api.app.orchestration import engine, policy_engine, provider, state_machine


def test_orchestration_code_has_no_secret_or_raw_prompt_leakage():
    for mod in [engine, policy_engine, provider, state_machine]:
        src = inspect.getsource(mod)
        assert "Authorization" not in src
        assert "Bearer " not in src
        assert "sk-proj-" not in src
        assert "DATABASE_URL" not in src
