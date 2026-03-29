"""Qwen (Alibaba Cloud DashScope) LLM implementation.

This module provides the Qwen LLM implementation that works with
Alibaba Cloud DashScope API via OpenAI-compatible interface.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

from src.libs.llm.base_llm import BaseLLM, ChatResponse, Message
from src.libs.llm.openai_llm import OpenAILLM


class QwenLLMError(RuntimeError):
    """Raised when Qwen API call fails."""


class QwenLLM(OpenAILLM):
    """Qwen LLM provider implementation.
    
    This class extends OpenAILLM to work with Alibaba Cloud DashScope API.
    It uses the OpenAI-compatible endpoint at dashscope.aliyuncs.com.
    
    Attributes:
        api_key: The API key for authentication (DASHSCOPE_API_KEY).
        base_url: The base URL for the DashScope API.
        model: The model identifier to use (e.g., qwen-turbo, qwen-plus, qwen-max).
        default_temperature: Default temperature for generation.
        default_max_tokens: Default max tokens for generation.
    
    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> llm = QwenLLM(settings)
        >>> response = llm.chat([Message(role='user', content='Hello')])
    """
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # Supported Qwen models
    SUPPORTED_MODELS = [
        "qwen-turbo",
        "qwen-plus", 
        "qwen-max",
        "qwen-max-longcontext",
        "qwen-vl-max-2025-04-02",
        "qwen2.5-72b-instruct",
        "qwen2.5-7b-instruct",
        "qwen2.5-1.5b-instruct",
    ]
    
    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen LLM provider.
        
        Args:
            settings: Application settings containing LLM configuration.
            api_key: Optional API key override (falls back to settings.llm.api_key or env var).
            base_url: Optional base URL override (defaults to DashScope endpoint).
            **kwargs: Additional configuration overrides.
        
        Raises:
            ValueError: If API key is not provided and not found in environment.
        
        Note:
            API key priority: explicit parameter > settings.llm.api_key > DASHSCOPE_API_KEY env var
        """
        # Get model from settings, default to qwen-plus if not specified
        model = getattr(settings.llm, 'model', None) or "qwen-plus"
        
        # API key: explicit > settings > DASHSCOPE_API_KEY env var
        settings_api_key = getattr(settings.llm, 'api_key', None)
        self.api_key = (
            api_key
            or (settings_api_key if settings_api_key else None)
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "Qwen (DashScope) API key not provided. Set in settings.yaml (llm.api_key), "
                "DASHSCOPE_API_KEY environment variable, or pass api_key parameter."
            )
        
        # Base URL: explicit parameter > settings.base_url > DEFAULT_BASE_URL
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = (
                getattr(settings.llm, 'base_url', None) 
                or self.DEFAULT_BASE_URL
            )
        
        # Store configuration
        self.model = model
        self.default_temperature = getattr(settings.llm, 'temperature', 0.0)
        self.default_max_tokens = getattr(settings.llm, 'max_tokens', 4096)
        
        # Qwen uses Bearer token auth (same as OpenAI)
        self._use_azure_auth = False
        
        # Store any additional kwargs for future use
        self._extra_config = kwargs
    
    def chat(
        self,
        messages: List[Message],
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Generate a chat completion using Qwen API.
        
        Args:
            messages: List of conversation messages.
            trace: Optional TraceContext for observability.
            **kwargs: Override parameters (temperature, max_tokens, etc.).
        
        Returns:
            ChatResponse with generated content and metadata.
        
        Raises:
            ValueError: If messages are invalid.
            QwenLLMError: If API call fails.
        """
        # Validate input
        self.validate_messages(messages)
        
        # Prepare request parameters
        temperature = kwargs.get("temperature", self.default_temperature)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
        model = kwargs.get("model", self.model)
        
        # Convert messages to API format
        api_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        # Make API call
        try:
            response_data = self._call_api(
                messages=api_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            # Parse response
            content = response_data["choices"][0]["message"]["content"]
            usage = response_data.get("usage")
            
            return ChatResponse(
                content=content,
                model=response_data.get("model", model),
                usage=usage,
                raw_response=response_data,
            )
        except KeyError as e:
            raise QwenLLMError(
                f"[Qwen] Unexpected response format: missing key {e}"
            ) from e
        except Exception as e:
            if isinstance(e, QwenLLMError):
                raise
            raise QwenLLMError(
                f"[Qwen] API call failed: {type(e).__name__}: {e}"
            ) from e

    def _call_api(
        self,
        messages: List[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Make the actual API call to Qwen (DashScope).
        
        This method is separated to allow easy mocking in tests.
        
        Args:
            messages: Messages in API format.
            model: Model identifier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens to generate.
        
        Returns:
            Raw API response as dictionary.
        
        Raises:
            QwenLLMError: If the API call fails.
        """
        import httpx
        
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "enable_thinking": False,  # Required for non-streaming calls with qwen3 models
        }
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    error_detail = self._parse_error_response(response)
                    raise QwenLLMError(
                        f"[Qwen] API error (HTTP {response.status_code}): {error_detail}"
                    )
                
                return response.json()
        except httpx.TimeoutException as e:
            raise QwenLLMError(
                f"[Qwen] Request timed out after 60 seconds"
            ) from e
        except httpx.RequestError as e:
            raise QwenLLMError(
                f"[Qwen] Connection failed: {type(e).__name__}: {e}"
            ) from e
