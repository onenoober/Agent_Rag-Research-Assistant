"""Qwen (Alibaba Cloud DashScope) Vision LLM implementation.

This module provides a Qwen Vision LLM implementation that works with
Alibaba Cloud DashScope API via OpenAI-compatible interface. Supports
multimodal models like qwen-omni-turbo, qwen-vl-max, etc.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Any, Optional

from src.libs.llm.base_llm import ChatResponse, Message
from src.libs.llm.base_vision_llm import BaseVisionLLM, ImageInput


class QwenVisionLLMError(RuntimeError):
    """Raised when Qwen Vision API call fails."""


class QwenVisionLLM(BaseVisionLLM):
    """Qwen Vision LLM provider implementation.

    This class extends the OpenAI-compatible protocol to work with
    Alibaba Cloud DashScope API for multimodal vision tasks.

    Supported models:
    - qwen-omni-turbo: Latest omnimodal model (text + image + audio)
    - qwen-vl-max: Vision-language model
    - qwen-vl-plus: Vision-language model

    Attributes:
        api_key: The API key for authentication (DASHSCOPE_API_KEY).
        base_url: The base URL for the DashScope API.
        model: The model identifier to use.
        max_image_size: Maximum image dimension in pixels for auto-compression.
        default_temperature: Default temperature for generation.
        default_max_tokens: Default max tokens for generation.

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> vision_llm = QwenVisionLLM(settings)
        >>> image = ImageInput(path="diagram.png")
        >>> response = vision_llm.chat_with_image("Describe this", image)
    """

    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MAX_IMAGE_SIZE = 2048  # pixels

    # Supported Qwen Vision models
    SUPPORTED_MODELS = [
        "qwen-omni-turbo",
        "qwen-omni-max",
        "qwen-vl-max",
        "qwen-vl-plus",
    ]

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_image_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen Vision LLM provider.

        Args:
            settings: Application settings containing vision_llm configuration.
            api_key: Optional API key override.
            base_url: Optional base URL override (defaults to DashScope endpoint).
            max_image_size: Maximum image dimension in pixels for auto-compression.
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If required configuration is missing.
        """
        # Get vision settings section
        vision_settings = getattr(settings, "vision_llm", None)

        # Temperature / max_tokens: vision_llm section > llm section defaults
        self.default_temperature = getattr(settings.llm, 'temperature', 0.0)
        # Qwen omni models have max_tokens range [10, 2048]
        llm_max_tokens = getattr(settings.llm, 'max_tokens', 4096)
        self.default_max_tokens = min(llm_max_tokens, 2048)  # Cap at 2048 for omni models

        # Model: explicit > vision_settings.model > llm.model
        vision_model = getattr(vision_settings, 'model', None) if vision_settings else None
        self.model = vision_model or getattr(settings.llm, 'model', None) or "qwen-omni-turbo"

        # Max image size
        vision_max_size = getattr(vision_settings, 'max_image_size', None) if vision_settings else None
        self.max_image_size = max_image_size or vision_max_size or self.DEFAULT_MAX_IMAGE_SIZE

        # API key: explicit > vision_settings > llm settings > DASHSCOPE_API_KEY env var
        self.api_key = api_key
        if not self.api_key and vision_settings:
            self.api_key = getattr(vision_settings, 'api_key', None)
        if not self.api_key:
            self.api_key = getattr(settings.llm, 'api_key', None)
        if not self.api_key:
            self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Qwen (DashScope) API key not provided. Set in settings.yaml "
                "(vision_llm.api_key or llm.api_key), DASHSCOPE_API_KEY environment variable, "
                "or pass api_key parameter."
            )

        # Base URL: explicit parameter > settings.base_url > DEFAULT_BASE_URL
        if base_url:
            self.base_url = base_url
        elif vision_settings and getattr(vision_settings, 'base_url', None):
            self.base_url = getattr(vision_settings, 'base_url', None)
        elif getattr(settings.llm, 'base_url', None):
            self.base_url = getattr(settings.llm, 'base_url', None)
        else:
            self.base_url = self.DEFAULT_BASE_URL

        self._extra_config = kwargs

    def chat_with_image(
        self,
        text: str,
        image: ImageInput,
        messages: Optional[list[Message]] = None,
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Generate a response based on text prompt and image input.

        Args:
            text: The text prompt or question about the image.
            image: The image input (path, bytes, or base64).
            messages: Optional conversation history for context.
            trace: Optional TraceContext for observability.
            **kwargs: Override parameters (temperature, max_tokens, etc.).

        Returns:
            ChatResponse containing the generated text and metadata.

        Raises:
            ValueError: If text or image input is invalid.
            QwenVisionLLMError: If API call fails.
        """
        # Validate inputs
        self.validate_text(text)
        self.validate_image(image)

        # Preprocess image (compress if needed)
        processed_image = self.preprocess_image(
            image,
            max_size=(self.max_image_size, self.max_image_size)
        )

        # Convert image to base64
        image_base64 = self._get_image_base64(processed_image)

        # Prepare request parameters
        temperature = kwargs.get("temperature", self.default_temperature)
        max_tokens = kwargs.get("max_tokens", self.default_max_tokens)

        # Build message list
        api_messages = []
        if messages:
            api_messages.extend([{"role": m.role, "content": m.content} for m in messages])

        # Add current text + image message
        current_message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": text
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{processed_image.mime_type};base64,{image_base64}"
                    }
                }
            ]
        }
        api_messages.append(current_message)

        # Make API call
        try:
            response_data = self._call_api(
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response_data["choices"][0]["message"]["content"]
            usage = response_data.get("usage")

            return ChatResponse(
                content=content,
                model=response_data.get("model", self.model),
                usage=usage,
                raw_response=response_data,
            )
        except KeyError as e:
            raise QwenVisionLLMError(
                f"[Qwen Vision] Unexpected response format: missing key {e}"
            ) from e
        except Exception as e:
            if isinstance(e, QwenVisionLLMError):
                raise
            raise QwenVisionLLMError(
                f"[Qwen Vision] API call failed: {type(e).__name__}: {e}"
            ) from e

    def preprocess_image(
        self,
        image: ImageInput,
        max_size: Optional[tuple[int, int]] = None,
    ) -> ImageInput:
        """Preprocess image before sending to Vision API.

        Compresses image if it exceeds max_size to reduce payload size.

        Args:
            image: The input image to preprocess.
            max_size: Maximum dimensions (width, height) in pixels.

        Returns:
            Preprocessed ImageInput with compressed data if needed.
        """
        if not max_size:
            return image

        try:
            from PIL import Image
        except ImportError:
            return image

        # Get image bytes
        if image.data:
            image_bytes = image.data
        elif image.path:
            image_bytes = Path(image.path).read_bytes()
        elif image.base64:
            return image
        else:
            return image

        # Load image and check size
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        max_width, max_height = max_size
        if width <= max_width and height <= max_height:
            return image

        # Calculate new size maintaining aspect ratio
        ratio = min(max_width / width, max_height / height)
        new_size = (int(width * ratio), int(height * ratio))

        # Resize image
        img_resized = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to bytes
        buffer = io.BytesIO()
        img_format = img.format or "PNG"
        img_resized.save(buffer, format=img_format)
        compressed_bytes = buffer.getvalue()

        return ImageInput(
            data=compressed_bytes,
            mime_type=image.mime_type
        )

    def _get_image_base64(self, image: ImageInput) -> str:
        """Convert ImageInput to base64 string."""
        try:
            if image.base64:
                return image.base64
            elif image.data:
                return base64.b64encode(image.data).decode("utf-8")
            elif image.path:
                image_bytes = Path(image.path).read_bytes()
                return base64.b64encode(image_bytes).decode("utf-8")
            else:
                raise ValueError("ImageInput has no valid data source")
        except Exception as e:
            raise QwenVisionLLMError(
                f"[Qwen Vision] Failed to encode image: {e}"
            ) from e

    def _call_api(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Make HTTP request to the Qwen Vision API.

        Args:
            messages: List of API-formatted messages.
            temperature: Generation temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            API response as dictionary.

        Raises:
            QwenVisionLLMError: If the API call fails.
        """
        import httpx

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload, headers=headers)

                if response.status_code != 200:
                    error_detail = self._parse_error_response(response)
                    raise QwenVisionLLMError(
                        f"[Qwen Vision] API error (HTTP {response.status_code}): {error_detail}"
                    )

                return response.json()
        except httpx.TimeoutException as e:
            raise QwenVisionLLMError(
                "[Qwen Vision] Request timed out after 60 seconds"
            ) from e
        except httpx.RequestError as e:
            raise QwenVisionLLMError(
                f"[Qwen Vision] Connection failed: {type(e).__name__}: {e}"
            ) from e

    def _parse_error_response(self, response: Any) -> str:
        """Parse error details from API response."""
        try:
            error_data = response.json()
            if "error" in error_data:
                error = error_data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            return response.text
        except Exception:
            return response.text or "Unknown error"
