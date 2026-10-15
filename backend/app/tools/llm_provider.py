"""
LLM Provider abstraction with priority-based fallback strategy.

Priority order:
1. Claude API (Anthropic)
2. Google Generative AI (Gemini)
3. Grok (XAI)
4. OpenAI (ChatGPT)
"""

import os
import logging
from typing import Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def real_api_key(name: str):
    """The env API key, or None when unset or still a template/dummy value
    ("your_..._here", "...Dummy...", "sk-ant-d01-dummy-...")."""
    value = (os.getenv(name) or "").strip()
    lowered = value.lower()
    if not value or "your_" in lowered or "dummy" in lowered or "placeholder" in lowered or len(value) < 20:
        return None
    return value

class LLMProvider(Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"
    OPENAI = "openai"

class RoundRobinLLMProvider:
    def __init__(self):
        self.providers = [LLMProvider.CLAUDE, LLMProvider.GEMINI, LLMProvider.GROK, LLMProvider.OPENAI]
        self.current_index = 0
        self.llm_instances = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all LLM providers lazily"""
        pass

    def _cached(self, key: str, factory):
        """Return the cached instance for ``key``, building it once.

        ``factory`` returns the client, or None when the provider is not
        configured. A failed or unconfigured initialisation caches None so it
        is not retried on every call; the cached value is always returned.
        """
        if key not in self.llm_instances:
            try:
                self.llm_instances[key] = factory()
            except Exception as e:
                logger.error(f"Failed to initialize {key}: {e}", exc_info=True)
                self.llm_instances[key] = None
        return self.llm_instances.get(key)

    def _get_gemini(self):
        """Lazy-load Gemini"""
        def build():
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = real_api_key("GEMINI_API_KEY")
            if not api_key or api_key == "AIzaSyDummy_For_Local_Dev":
                logger.warning("GEMINI_API_KEY not set or is dummy key, skipping Gemini")
                return None
            return ChatGoogleGenerativeAI(api_key=api_key, model="gemini-1.5-flash", max_retries=1)
        return self._cached("gemini", build)

    def _get_claude(self):
        """Lazy-load Claude"""
        def build():
            from langchain_anthropic import ChatAnthropic
            api_key = real_api_key("ANTHROPIC_API_KEY")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY not set")
                return None
            return ChatAnthropic(api_key=api_key, model="claude-sonnet-5-5", max_tokens=2048)
        return self._cached("claude", build)

    def _get_grok(self):
        """Lazy-load Grok"""
        def build():
            from xai_sdk import XAIClient
            api_key = real_api_key("XAI_API_KEY")
            if not api_key:
                logger.warning("XAI_API_KEY not set")
                return None
            return XAIClient(api_key=api_key)
        return self._cached("grok", build)

    def _get_openai(self):
        """Lazy-load OpenAI (ChatGPT)"""
        def build():
            from langchain_openai import ChatOpenAI
            api_key = real_api_key("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not set")
                return None
            return ChatOpenAI(api_key=api_key, model="gpt-4-turbo", max_tokens=2048)
        return self._cached("openai", build)

    def get_next_provider(self):
        """Get next provider in round-robin order"""
        provider = self.providers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.providers)
        return provider

    def get_llm(self):
        """Get working LLM with automatic fallback"""
        attempts = 0
        while attempts < len(self.providers):
            provider = self.get_next_provider()

            if provider == LLMProvider.CLAUDE:
                llm = self._get_claude()
            elif provider == LLMProvider.GEMINI:
                llm = self._get_gemini()
            elif provider == LLMProvider.GROK:
                llm = self._get_grok()
            elif provider == LLMProvider.OPENAI:
                llm = self._get_openai()
            else:
                llm = None

            if llm is not None:
                logger.info(f"Using LLM provider: {provider.value}")
                return llm, provider

            attempts += 1

        # All providers failed
        logger.error("All LLM providers failed")
        return None, None

    def get_llm_with_fallback(self, attempt=0):
        """Get LLM with error handling"""
        llm, provider = self.get_llm()
        if llm is None:
            raise RuntimeError("No LLM providers available")
        return llm, provider

# Global instance
_llm_provider = RoundRobinLLMProvider()

def get_llm():
    """Get working LLM with automatic fallback"""
    llm, provider = _llm_provider.get_llm()
    if llm is None:
        raise RuntimeError("No LLM providers available")
    return llm, provider

def invoke_llm(prompt: str, provider_hint: Optional[LLMProvider] = None):
    """Invoke LLM with automatic fallback"""
    llm, provider = get_llm()
    try:
        result = llm.invoke(prompt)
        logger.info(f"LLM invocation successful with {provider.value}")
        return result, provider
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"LLM invocation failed with {provider.value}: {e}")
        raise
