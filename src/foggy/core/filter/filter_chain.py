"""Filter chain implementation for Foggy Framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class FoggyStep(ABC, Generic[T, R]):
    """Abstract base class for filter steps.

    Each step in the filter chain implements this interface.
    """

    @abstractmethod
    async def process(self, context: T, chain: "FoggyFilterChain[T]") -> R:
        """Process the request and pass to next step.

        Args:
            context: Request context
            chain: Filter chain for calling next step

        Returns:
            Result after processing
        """
        pass


class FoggyFilter(FoggyStep[T, R]):
    """Base filter class with before/after hooks.

    Override do_filter for custom filtering logic.
    """

    async def process(self, context: T, chain: "FoggyFilterChain[T]") -> R:
        """Process by calling before_filter, chain.do_filter, then after_filter."""
        await self.before_filter(context)
        try:
            result = await chain.do_filter(context)
            await self.after_filter(context, result)
            return result
        except Exception as e:
            await self.on_error(context, e)
            raise

    async def before_filter(self, context: T) -> None:
        """Called before passing to next filter.

        Override to implement pre-processing logic.
        """
        pass

    async def after_filter(self, context: T, result: R) -> None:
        """Called after receiving result from next filter.

        Override to implement post-processing logic.
        """
        pass

    async def on_error(self, context: T, error: Exception) -> None:
        """Called when an error occurs.

        Override to implement error handling.
        """
        pass


@dataclass
class FoggyFilterChain(Generic[T]):
    """Filter chain for executing a sequence of filters.

    Usage:
        filters = [AuthFilter(), LoggingFilter(), ValidationFilter()]
        chain = FoggyFilterChain(filters)
        result = await chain.execute(context)
    """

    filters: List[FoggyStep[T, Any]]
    _index: int = 0
    _final_handler: Optional[Callable[[T], Any]] = None

    async def do_filter(self, context: T) -> Any:
        """Execute the next filter in chain.

        Args:
            context: Request context

        Returns:
            Result from next filter or final handler
        """
        if self._index < len(self.filters):
            filter_ = self.filters[self._index]
            self._index += 1
            return await filter_.process(context, self)

        # End of chain, call final handler
        if self._final_handler:
            if callable(self._final_handler):
                result = self._final_handler(context)
                if hasattr(result, "__await__"):
                    return await result
                return result

        return None

    async def execute(
        self,
        context: T,
        final_handler: Optional[Callable[[T], Any]] = None,
    ) -> Any:
        """Execute the filter chain.

        Args:
            context: Request context
            final_handler: Handler to call at end of chain

        Returns:
            Final result
        """
        # Reset index for new execution
        self._index = 0
        self._final_handler = final_handler
        return await self.do_filter(context)

    def reset(self) -> None:
        """Reset the chain for reuse."""
        self._index = 0
        self._final_handler = None

    @classmethod
    def create(cls, filters: List[FoggyStep[T, Any]]) -> "FoggyFilterChain[T]":
        """Create a new filter chain with the given filters."""
        return cls(filters=filters)


class SimpleFilter(FoggyFilter[T, R]):
    """Simple filter that wraps a callable."""

    def __init__(
        self,
        name: str,
        before: Optional[Callable[[T], None]] = None,
        after: Optional[Callable[[T, R], None]] = None,
        error: Optional[Callable[[T, Exception], None]] = None,
    ) -> None:
        self.name = name
        self._before = before
        self._after = after
        self._error = error

    async def before_filter(self, context: T) -> None:
        if self._before:
            result = self._before(context)
            if hasattr(result, "__await__"):
                await result

    async def after_filter(self, context: T, result: R) -> None:
        if self._after:
            res = self._after(context, result)
            if hasattr(res, "__await__"):
                await res

    async def on_error(self, context: T, error: Exception) -> None:
        if self._error:
            res = self._error(context, error)
            if hasattr(res, "__await__"):
                await res