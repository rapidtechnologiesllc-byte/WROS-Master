"""
LLM Provider abstraction with round-robin fallback strategy.

Primary: Google Generative AI (Gemini)
Backup 2: Claude API (Anthropic)
Backup 3: Grok (XAI)
"""

import os
import logging
from typing import Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    GEMINI = "gemini"
    CLAUDE = "claude"
    GROK = "grok"


class RoundRobinLLMProvider:
    def __init__(self):
        self.providers = [LLMProvider.GEMINI, LLMProvider.CLAUDE, LLMProvider.GROK]
        self.current_index = 0
        self.llm_instances = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all LLM providers lazily"""
        pass

    def _get_gemini(self):
        """Lazy-load Gemini"""
        if "gemini" not in self.llm_instances:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = os.getenv("GEMINI_API_KEY")
                # Skip if API key not set or is dummy key
                if not api_key or api_key == "AIzaSyDummy_For_Local_Dev":
                    logger.warning("GEMINI_API_KEY not set or is dummy key, skipping Gemini")
                    return None
                self.llm_instances["gemini"] = ChatGoogleGenerativeAI(
                    api_key=api_key,
                    model="gemini-1.5-flash",
                    max_retries=1
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.llm_instances["gemini"] = None
        return self.llm_instances["gemini"]

    def _get_claude(self):
        """Lazy-load Claude"""
        if "claude" not in self.llm_instances:
            try:
                from langchain_anthropic import ChatAnthropic
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not set")
                    return None
                self.llm_instances["claude"] = ChatAnthropic(
                    api_key=api_key,
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048
                )
            except Exception as e:
                logger.error(f"Failed to initialize Claude: {e}")
                self.llm_instances["claude"] = None
        return self.llm_instances["claude"]

    def _get_grok(self):
        """Lazy-load Grok"""
        if "grok" not in self.llm_instances:
            try:
                from xai_sdk import XAIClient
                api_key = os.getenv("XAI_API_KEY")
                if not api_key:
                    logger.warning("XAI_API_KEY not set")
                    return None
                self.llm_instances["grok"] = XAIClient(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Grok: {e}")
                self.llm_instances["grok"] = None
        return self.llm_instances["grok"]

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

            if provider == LLMProvider.GEMINI:
                llm = self._get_gemini()
            elif provider == LLMProvider.CLAUDE:
                llm = self._get_claude()
            elif provider == LLMProvider.GROK:
                llm = self._get_grok()
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
        logger.error(f"LLM invocation failed with {provider.value}: {e}")
        raise
