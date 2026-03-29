"""Evaluator registry with decorator-based automatic registration.

This module provides a pluggable registry system for Evaluators:
- Decorators: @register_evaluator(name) for automatic registration
- Type-safe: Validates BaseEvaluator subclass inheritance
- Lazy loading: Supports lazy imports for heavy dependencies
- Priority system: Allows ordering of evaluators

Design Principles Applied:
- Plugin Architecture: New evaluators can be added without modifying existing code
- Convention over Configuration: Simply decorate a class to make it available
- Lazy Loading: Heavy dependencies (ragas) are only imported when needed

Example Usage::

    # In evaluators/hits_evaluator.py
    from src.evaluation.registry import register_evaluator

    @register_evaluator("hits")
    class HitsEvaluator(BaseEvaluator):
        ...

    # In factory.py or anywhere
    from src.evaluation.registry import get_evaluator_registry
    registry = get_evaluator_registry()
    evaluator = registry.create("hits", settings=settings)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.evaluation.evaluators.base import BaseEvaluator

logger = logging.getLogger(__name__)


class EvaluatorRegistry:
    """Central registry for all Evaluator implementations.

    This class maintains a mapping of evaluator names to their implementations.
    Supports both direct class registration and lazy-loading registration.

    Attributes:
        _evaluators: Dict mapping evaluator names to their classes.
        _lazy_loaders: Dict mapping names to factory functions for lazy loading.
        _metadata: Dict mapping names to metadata (description, priority, etc.).
    """

    def __init__(self) -> None:
        self._evaluators: Dict[str, Type["BaseEvaluator"]] = {}
        self._lazy_loaders: Dict[str, Callable[[], Type["BaseEvaluator"]]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._eager_loaded: set = set()  # Track which evaluators were eagerly loaded

    def register(
        self,
        name: str,
        evaluator_class: Type["BaseEvaluator"],
        *,
        description: str = "",
        priority: int = 100,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register an evaluator class directly.

        Args:
            name: Unique identifier for the evaluator.
            evaluator_class: The BaseEvaluator subclass to register.
            description: Human-readable description of the evaluator.
            priority: Lower values = higher priority in auto-discovery.
            tags: Optional list of tags for categorization.

        Raises:
            ValueError: If name is empty or evaluator_class doesn't inherit BaseEvaluator.
            TypeError: If evaluator_class is not a class.
        """
        if not name or not name.strip():
            raise ValueError("Evaluator name cannot be empty")

        if not isinstance(evaluator_class, type):
            raise TypeError(
                f"Expected a class, got {type(evaluator_class).__name__}. "
                "Use @register_evaluator decorator instead."
            )

        # Import here to avoid circular dependency
        from src.evaluation.evaluators.base import BaseEvaluator as _BaseEvaluator

        if not issubclass(evaluator_class, _BaseEvaluator):
            mro_names = [c.__name__ for c in evaluator_class.__mro__[:-1]]
            raise ValueError(
                f"Evaluator class {evaluator_class.__name__} must inherit from BaseEvaluator. "
                f"Got MRO: {mro_names}"
            )

        normalized_name = name.lower().strip()
        self._evaluators[normalized_name] = evaluator_class
        self._eager_loaded.add(normalized_name)

        self._metadata[normalized_name] = {
            "description": description or f"{evaluator_class.__name__} evaluator",
            "priority": priority,
            "tags": tags or [],
            "lazy": False,
            "class": evaluator_class,
        }

        logger.debug(
            "Registered evaluator '%s' (class: %s, priority: %d)",
            normalized_name,
            evaluator_class.__name__,
            priority,
        )

    def register_lazy(
        self,
        name: str,
        loader: Callable[[], Type["BaseEvaluator"]],
        *,
        description: str = "",
        priority: int = 100,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register an evaluator with lazy loading (import on first use).

        Use this for evaluators with heavy dependencies (e.g., ragas).

        Args:
            name: Unique identifier for the evaluator.
            loader: Factory function that returns the evaluator class.
            description: Human-readable description of the evaluator.
            priority: Lower values = higher priority in auto-discovery.
            tags: Optional list of tags for categorization.

        Raises:
            ValueError: If name is empty or loader is not callable.
        """
        if not name or not name.strip():
            raise ValueError("Evaluator name cannot be empty")

        if not callable(loader):
            raise TypeError(f"Loader must be callable, got {type(loader).__name__}")

        normalized_name = name.lower().strip()
        self._lazy_loaders[normalized_name] = loader

        self._metadata[normalized_name] = {
            "description": description or f"Lazy-registered evaluator: {name}",
            "priority": priority,
            "tags": tags or [],
            "lazy": True,
        }

        logger.debug(
            "Registered lazy evaluator '%s' (priority: %d)",
            normalized_name,
            priority,
        )

    def unregister(self, name: str) -> bool:
        """Unregister an evaluator by name.

        Args:
            name: The name of the evaluator to unregister.

        Returns:
            True if the evaluator was removed, False if it wasn't registered.
        """
        normalized_name = name.lower().strip()
        removed = False

        if normalized_name in self._evaluators:
            del self._evaluators[normalized_name]
            removed = True

        if normalized_name in self._lazy_loaders:
            del self._lazy_loaders[normalized_name]
            removed = True

        if normalized_name in self._metadata:
            del self._metadata[normalized_name]

        if removed:
            logger.debug("Unregistered evaluator '%s'", normalized_name)

        return removed

    def get(self, name: str) -> Optional[Type["BaseEvaluator"]]:
        """Get an evaluator class by name.

        Args:
            name: The name of the evaluator.

        Returns:
            The evaluator class, or None if not registered.
        """
        normalized_name = name.lower().strip()

        # Check eager-loaded first
        if normalized_name in self._evaluators:
            return self._evaluators[normalized_name]

        # Try lazy loading
        if normalized_name in self._lazy_loaders:
            try:
                evaluator_class = self._lazy_loaders[normalized_name]()
                # Cache for next call
                self._evaluators[normalized_name] = evaluator_class
                self._eager_loaded.add(normalized_name)
                del self._lazy_loaders[normalized_name]
                return evaluator_class
            except ImportError as e:
                logger.warning(
                    "Failed to lazy-load evaluator '%s': %s",
                    normalized_name,
                    e,
                )
                return None

        return None

    def create(
        self,
        name: str,
        *args: Any,
        settings: Optional[Any] = None,
        **kwargs: Any,
    ) -> Optional["BaseEvaluator"]:
        """Create an instance of the named evaluator.

        Args:
            name: The name of the evaluator to instantiate.
            *args: Positional arguments passed to the evaluator constructor.
            settings: Application settings (convenience arg).
            **kwargs: Keyword arguments passed to the evaluator constructor.

        Returns:
            An instance of the evaluator, or None if not found.

        Raises:
            RuntimeError: If evaluator is found but instantiation fails.
        """
        evaluator_class = self.get(name)

        if evaluator_class is None:
            return None

        # Merge settings if provided
        if settings is not None:
            kwargs.setdefault("settings", settings)

        try:
            return evaluator_class(*args, **kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Failed to instantiate evaluator '{name}': {e}"
            ) from e

    def list_evaluators(self, include_lazy: bool = True) -> List[str]:
        """List all registered evaluator names.

        Args:
            include_lazy: If True, include lazy-loaded evaluators.

        Returns:
            Sorted list of evaluator names.
        """
        names = set(self._evaluators.keys())
        if include_lazy:
            names.update(self._lazy_loaders.keys())
        return sorted(names)

    def list_with_metadata(self, include_lazy: bool = True) -> List[Dict[str, Any]]:
        """List evaluators with their metadata.

        Args:
            include_lazy: If True, include lazy-loaded evaluators.

        Returns:
            List of dicts with 'name', 'description', 'priority', 'tags'.
        """
        result = []

        for name in self._metadata:
            if not include_lazy and self._metadata[name].get("lazy"):
                continue
            result.append({
                "name": name,
                **self._metadata[name],
            })

        # Sort by priority
        result.sort(key=lambda x: x.get("priority", 100))

        return result

    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific evaluator.

        Args:
            name: The name of the evaluator.

        Returns:
            Metadata dict, or None if not registered.
        """
        normalized_name = name.lower().strip()
        return self._metadata.get(normalized_name)

    def __contains__(self, name: str) -> bool:
        """Check if an evaluator is registered."""
        normalized_name = name.lower().strip()
        return (
            normalized_name in self._evaluators
            or normalized_name in self._lazy_loaders
        )

    def __len__(self) -> int:
        """Return the number of registered evaluators."""
        return len(self._evaluators) + len(self._lazy_loaders)


# Global registry instance
_registry: Optional[EvaluatorRegistry] = None


def get_evaluator_registry() -> EvaluatorRegistry:
    """Get the global evaluator registry instance.

    Returns:
        The singleton EvaluatorRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = EvaluatorRegistry()
        _register_default_evaluators(_registry)
    return _registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None


def _register_default_evaluators(registry: EvaluatorRegistry) -> None:
    """Register the built-in evaluators.

    This function is called automatically when get_evaluator_registry()
    is first called. It registers the default evaluators that come
    with the framework.
    """
    # Eager-loaded evaluators (no external dependencies)
    from src.evaluation.evaluators.custom import CustomEvaluator
    from src.evaluation.evaluators.base import NoneEvaluator

    registry.register(
        "custom",
        CustomEvaluator,
        description="Lightweight retrieval metrics (hit_rate, mrr)",
        priority=50,
        tags=["retrieval", "fast", "builtin"],
    )

    registry.register(
        "none",
        NoneEvaluator,
        description="No-op evaluator that returns empty metrics",
        priority=200,
        tags=["placeholder", "builtin"],
    )

    # Lazy-loaded evaluators (heavy dependencies)
    registry.register_lazy(
        "ragas",
        _load_ragas_evaluator,
        description="RAGAS LLM-as-Judge metrics (faithfulness, answer_relevancy, context_precision)",
        priority=30,
        tags=["llm-judge", "ragas", "quality"],
    )

    registry.register_lazy(
        "composite",
        _load_composite_evaluator,
        description="Composite evaluator combining multiple backends",
        priority=150,
        tags=["composite", "multi-backend"],
    )


def _load_ragas_evaluator() -> Type["BaseEvaluator"]:
    """Lazy loader for RagasEvaluator."""
    from src.evaluation.evaluators.ragas import RagasEvaluator
    return RagasEvaluator


def _load_composite_evaluator() -> Type["BaseEvaluator"]:
    """Lazy loader for CompositeEvaluator."""
    from src.evaluation.evaluators.composite import CompositeEvaluator
    return CompositeEvaluator


def register_evaluator(
    name: str,
    *,
    description: str = "",
    priority: int = 100,
    tags: Optional[List[str]] = None,
) -> Callable[[Type["BaseEvaluator"]], Type["BaseEvaluator"]]:
    """Decorator to register an Evaluator class.

    This is the recommended way to register custom evaluators.

    Args:
        name: Unique identifier for the evaluator.
        description: Human-readable description.
        priority: Lower values = higher priority.
        tags: Optional tags for categorization.

    Returns:
        A decorator function that registers the class.

    Example::

        @register_evaluator("my_custom_eval", description="My custom evaluator")
        class MyCustomEvaluator(BaseEvaluator):
            ...

        # Or with more options:
        @register_evaluator(
            "semantic_match",
            description="Semantic similarity evaluator",
            priority=40,
            tags=["semantic", "experimental"],
        )
        class SemanticMatchEvaluator(BaseEvaluator):
            ...
    """
    def decorator(cls: Type["BaseEvaluator"]) -> Type["BaseEvaluator"]:
        registry = get_evaluator_registry()
        registry.register(
            name,
            cls,
            description=description,
            priority=priority,
            tags=tags,
        )
        return cls

    return decorator


def register_evaluator_lazy(
    name: str,
    loader: Callable[[], Type["BaseEvaluator"]],
    *,
    description: str = "",
    priority: int = 100,
    tags: Optional[List[str]] = None,
) -> None:
    """Register an evaluator with lazy loading via decorator.

    Use this for evaluators with heavy dependencies.

    Args:
        name: Unique identifier for the evaluator.
        loader: Factory function returning the evaluator class.
        description: Human-readable description.
        priority: Lower values = higher priority.
        tags: Optional tags for categorization.

    Example::

        def _load_heavy_evaluator():
            from my_evaluators.heavy import HeavyEvaluator
            return HeavyEvaluator

        register_evaluator_lazy("heavy", _load_heavy_evaluator, description="Heavy evaluator")
    """
    registry = get_evaluator_registry()
    registry.register_lazy(
        name,
        loader,
        description=description,
        priority=priority,
        tags=tags,
    )


# ── Convenience methods for common operations ─────────────────────────────────

def create_evaluator(
    name: str,
    *args: Any,
    settings: Optional[Any] = None,
    **kwargs: Any,
) -> Optional["BaseEvaluator"]:
    """Create an evaluator by name using the global registry.

    This is a convenience function that uses the global registry.

    Args:
        name: Name of the evaluator to create.
        *args: Positional arguments for the evaluator.
        settings: Application settings.
        **kwargs: Keyword arguments for the evaluator.

    Returns:
        An evaluator instance, or None if not found.
    """
    return get_evaluator_registry().create(name, *args, settings=settings, **kwargs)


def list_available_evaluators() -> List[str]:
    """List all available evaluator names."""
    return get_evaluator_registry().list_evaluators()


def get_evaluator_info(name: str) -> Optional[Dict[str, Any]]:
    """Get detailed info about an evaluator."""
    return get_evaluator_registry().get_metadata(name)
