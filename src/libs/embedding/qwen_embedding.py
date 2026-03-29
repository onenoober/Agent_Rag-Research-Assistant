"""Qwen (Alibaba Cloud DashScope) Embedding implementation.

This module provides the Qwen Embedding implementation that works with
Alibaba Cloud DashScope API via OpenAI-compatible interface.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

from src.libs.embedding.base_embedding import BaseEmbedding
from src.libs.embedding.openai_embedding import OpenAIEmbedding


class QwenEmbeddingError(RuntimeError):
    """Raised when Qwen Embeddings API call fails."""


class QwenEmbedding(OpenAIEmbedding):
    """Qwen Embedding provider implementation.
    
    This class extends OpenAIEmbedding to work with Alibaba Cloud DashScope API.
    It uses the OpenAI-compatible endpoint at dashscope.aliyuncs.com.
    
    Attributes:
        api_key: The API key for authentication (DASHSCOPE_API_KEY).
        base_url: The base URL for the DashScope API.
        model: The model identifier to use (e.g., text-embedding-v3).
        dimensions: Optional dimension setting (only for text-embedding-v3).
    
    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> embedding = QwenEmbedding(settings)
        >>> vectors = embedding.embed(["hello world", "test"])
    """
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # Supported Qwen embedding models
    SUPPORTED_MODELS = [
        "text-embedding-v3",
        "text-embedding-v2",
        "text-embedding-ada-002",  # Also supported for backward compatibility
    ]
    
    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen Embedding provider.
        
        Args:
            settings: Application settings containing Embedding configuration.
            api_key: Optional API key override (falls back to settings.embedding.api_key or env var).
            base_url: Optional base URL override (defaults to DashScope endpoint).
            **kwargs: Additional configuration overrides.
        
        Raises:
            ValueError: If API key is not provided and not found in environment.
        
        Note:
            API key priority: explicit parameter > settings.embedding.api_key > DASHSCOPE_API_KEY env var
            Dimensions: Qwen text-embedding-v3 supports 256, 512, 1024, 1536, 2048, 3072, 4096
        """
        # Get model from settings, default to text-embedding-v3 if not specified
        model = getattr(settings.embedding, 'model', None) or "text-embedding-v3"
        
        # API key: explicit > settings > DASHSCOPE_API_KEY env var
        settings_api_key = getattr(settings.embedding, 'api_key', None)
        resolved_api_key = (
            api_key
            or (settings_api_key if settings_api_key else None)
            or os.environ.get("DASHSCOPE_API_KEY")
        )
        if not resolved_api_key:
            raise ValueError(
                "Qwen (DashScope) API key not provided. Set in settings.yaml (embedding.api_key), "
                "DASHSCOPE_API_KEY environment variable, or pass api_key parameter."
            )
        
        # Base URL: explicit parameter > settings.base_url > DEFAULT_BASE_URL
        if base_url:
            resolved_base_url = base_url
        else:
            settings_base_url = getattr(settings.embedding, 'base_url', None)
            resolved_base_url = settings_base_url if settings_base_url else self.DEFAULT_BASE_URL
        
        # Store configuration
        self.model = model
        
        # Extract optional dimensions setting
        self.dimensions = getattr(settings.embedding, 'dimensions', None)
        
        # Qwen uses Bearer token auth (same as OpenAI)
        self._use_azure_auth = False
        
        # Store API key and base_url for OpenAIEmbedding.embed() method
        self.api_key = resolved_api_key
        self.base_url = resolved_base_url
        
        # Store any additional kwargs for future use
        self._extra_config = kwargs
