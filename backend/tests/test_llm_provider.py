"""llm_provider's lazy getters return the cached client. They used to return None on every
successful build (the return sat inside the except) and on every cached call."""
import sys
import types

from app.tools import llm_provider
from app.tools.llm_provider import RoundRobinLLMProvider

KEY = "sk-real-looking-key-0123456789abcdef"


def _fake_module(monkeypatch, module_name, class_name, built):
    class Client:
        def __init__(self, **kwargs):
            built.append(kwargs)

    module = types.ModuleType(module_name)
    setattr(module, class_name, Client)
    monkeypatch.setitem(sys.modules, module_name, module)
    return Client


def test_built_client_is_returned_and_then_served_from_cache(monkeypatch):
    built = []
    client_cls = _fake_module(monkeypatch, "langchain_anthropic", "ChatAnthropic", built)
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    provider = RoundRobinLLMProvider()
    first = provider._get_claude()
    assert isinstance(first, client_cls)
    assert provider._get_claude() is first and len(built) == 1


def test_unconfigured_provider_is_none_and_not_rebuilt(monkeypatch):
    built = []
    _fake_module(monkeypatch, "langchain_openai", "ChatOpenAI", built)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = RoundRobinLLMProvider()
    assert provider._get_openai() is None and provider._get_openai() is None
    assert built == [] and provider.llm_instances == {"openai": None}


def test_failed_initialisation_is_cached_as_none(monkeypatch):
    calls = []

    class Broken:
        def __init__(self, **kwargs):
            calls.append(1)
            raise RuntimeError("bad SDK")

    module = types.ModuleType("langchain_google_genai")
    module.ChatGoogleGenerativeAI = Broken
    monkeypatch.setitem(sys.modules, "langchain_google_genai", module)
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    provider = RoundRobinLLMProvider()
    assert provider._get_gemini() is None and provider._get_gemini() is None
    assert calls == [1]


def test_get_llm_returns_the_first_working_provider(monkeypatch):
    built = []
    _fake_module(monkeypatch, "langchain_anthropic", "ChatAnthropic", built)
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    for name in ("GEMINI_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    llm, provider = RoundRobinLLMProvider().get_llm()
    assert llm is not None and provider is llm_provider.LLMProvider.CLAUDE
