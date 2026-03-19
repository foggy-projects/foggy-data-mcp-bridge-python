"""Multi-thread executor for Foggy Framework."""

import asyncio
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, List, Optional, TypeVar, Union

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class MTask(Generic[T]):
    """Task abstraction for multi-thread execution."""

    id: str
    name: str
    func: Callable[..., T]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    result: Optional[T] = None
    error: Optional[Exception] = None
    completed: bool = False

    def execute(self) -> T:
        """Execute the task."""
        try:
            self.result = self.func(*self.args, **self.kwargs)
            self.completed = True
            return self.result
        except Exception as e:
            self.error = e
            raise


class MultiThreadExecutor:
    """Multi-thread executor for parallel task execution.

    Usage:
        executor = MultiThreadExecutor(max_workers=4)

        # Submit tasks
        future1 = executor.submit(task1, arg1, arg2)
        future2 = executor.submit(task2, arg3)

        # Wait for results
        results = executor.map([task1, task2, task3])

        # Shutdown
        executor.shutdown()
    """

    def __init__(self, max_workers: Optional[int] = None) -> None:
        """Initialize executor.

        Args:
            max_workers: Maximum number of worker threads (default: CPU count)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: List[Future] = []

    def submit(
        self,
        func: Callable[..., R],
        *args,
        **kwargs,
    ) -> Future[R]:
        """Submit a function for execution.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future object
        """
        future = self._executor.submit(func, *args, **kwargs)
        self._futures.append(future)
        return future

    def submit_task(self, task: MTask[R]) -> Future[R]:
        """Submit a MTask for execution.

        Args:
            task: Task to execute

        Returns:
            Future object
        """
        return self.submit(task.func, *task.args, **task.kwargs)

    def map(
        self,
        func: Callable[..., R],
        iterable: list,
        timeout: Optional[float] = None,
    ) -> list[R]:
        """Apply function to each item in iterable in parallel.

        Args:
            func: Function to apply
            iterable: Items to process
            timeout: Timeout in seconds

        Returns:
            List of results
        """
        return list(self._executor.map(func, iterable, timeout=timeout))

    def execute_tasks(
        self,
        tasks: List[MTask],
        timeout: Optional[float] = None,
    ) -> List[MTask]:
        """Execute multiple tasks in parallel.

        Args:
            tasks: Tasks to execute
            timeout: Timeout in seconds

        Returns:
            List of completed tasks
        """
        futures = [self.submit_task(task) for task in tasks]

        # Wait for all futures
        for future, task in zip(futures, tasks):
            try:
                task.result = future.result(timeout=timeout)
                task.completed = True
            except Exception as e:
                task.error = e

        return tasks

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor.

        Args:
            wait: Whether to wait for pending tasks
        """
        self._executor.shutdown(wait=wait)
        self._futures.clear()

    def __enter__(self) -> "MultiThreadExecutor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()


async def run_in_threadpool(func: Callable[..., R], *args, **kwargs) -> R:
    """Run a synchronous function in threadpool.

    This is useful for running blocking operations in async context.

    Args:
        func: Function to run
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)


async def gather_with_concurrency(
    n: int,
    *coros,
    return_exceptions: bool = False,
) -> list:
    """Run coroutines with limited concurrency.

    Args:
        n: Maximum concurrent tasks
        *coros: Coroutines to run
        return_exceptions: Whether to return exceptions instead of raising

    Returns:
        List of results
    """
    semaphore = asyncio.Semaphore(n)

    async def run_with_semaphore(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *[run_with_semaphore(c) for c in coros],
        return_exceptions=return_exceptions,
    )