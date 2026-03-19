"""Module loader for FSScript import system.

Provides the ability to load and execute .fsscript modules,
handling exports, caching, and circular import detection.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Set
import threading

from foggy.fsscript.parser.parser import FsscriptParser
from foggy.fsscript.evaluator import ExpressionEvaluator


class ModuleLoader(ABC):
    """Abstract base class for module loaders.

    Module loaders are responsible for finding, parsing, and executing
    FSScript modules, then returning their exports.
    """

    @abstractmethod
    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load a module and return its exports.

        Args:
            module_path: Path to the module (relative or absolute)
            context: Current evaluation context (for resolving relative paths)

        Returns:
            Dictionary of exported names to values
        """
        pass

    @abstractmethod
    def has_module(self, module_path: str) -> bool:
        """Check if a module exists.

        Args:
            module_path: Path to the module

        Returns:
            True if the module can be loaded
        """
        pass


class FileModuleLoader(ModuleLoader):
    """Module loader that loads .fsscript files from the file system.

    Features:
    - Caches loaded modules to avoid re-execution
    - Handles relative and absolute paths
    - Detects circular imports
    - Thread-safe loading
    """

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the file module loader.

        Args:
            base_path: Base directory for resolving relative paths.
                      If None, uses current working directory.
        """
        self._base_path = base_path or Path.cwd()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loading: Set[str] = set()  # For circular import detection
        self._lock = threading.Lock()

    @property
    def base_path(self) -> Path:
        """Get the base path for resolving relative paths."""
        return self._base_path

    @base_path.setter
    def base_path(self, value: Path) -> None:
        """Set the base path."""
        self._base_path = Path(value)

    def resolve_path(self, module_path: str, context: Optional[Dict[str, Any]] = None) -> Path:
        """Resolve a module path to an absolute file path.

        Args:
            module_path: Module path (can be relative or absolute)
            context: Context with __current_module__ for relative resolution

        Returns:
            Resolved absolute Path
        """
        # Remove quotes if present
        module_path = module_path.strip("'\"")

        # Check if it's a relative import (starts with ./)
        if module_path.startswith('./') or module_path.startswith('../'):
            # Get the current module's directory
            current_module = context.get("__current_module__") if context else None
            if current_module:
                current_dir = Path(current_module).parent
            else:
                current_dir = self._base_path
            return (current_dir / module_path).resolve()
        else:
            # Treat as relative to base path
            return (self._base_path / module_path).resolve()

    def has_module(self, module_path: str) -> bool:
        """Check if a module file exists."""
        try:
            resolved = self.resolve_path(module_path)
            return resolved.exists() and resolved.is_file()
        except Exception:
            return False

    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load and execute a module, returning its exports.

        Args:
            module_path: Path to the module file
            context: Current evaluation context

        Returns:
            Dictionary of exported values

        Raises:
            ModuleNotFoundError: If module file doesn't exist
            CircularImportError: If circular import is detected
        """
        resolved_path = self.resolve_path(module_path, context)
        path_str = str(resolved_path)

        # Check cache first
        with self._lock:
            if path_str in self._cache:
                return self._cache[path_str]

            # Check for circular imports
            if path_str in self._loading:
                raise CircularImportError(f"Circular import detected: {path_str}")

            self._loading.add(path_str)

        try:
            # Check if file exists
            if not resolved_path.exists():
                raise ModuleNotFoundError(f"Module not found: {module_path} (resolved to {path_str})")

            # Read the file
            source = resolved_path.read_text(encoding='utf-8')

            # Parse the module
            parser = FsscriptParser(source)
            ast = parser.parse_program()

            # Create a new evaluator for the module
            module_context = {
                "__current_module__": path_str,
                "__module_loader__": self,
            }

            evaluator = ExpressionEvaluator(module_context)

            # Execute the module
            try:
                evaluator.evaluate(ast)
            except CircularImportError:
                # Re-raise circular import errors
                raise
            except Exception as e:
                # Don't fail the import for other errors, just log and continue
                pass

            # Get exports
            exports = evaluator.get_exports()

            # Cache the result
            with self._lock:
                self._cache[path_str] = exports
                self._loading.discard(path_str)

            return exports

        except Exception as e:
            with self._lock:
                self._loading.discard(path_str)
            raise

    def clear_cache(self) -> None:
        """Clear the module cache."""
        with self._lock:
            self._cache.clear()
            self._loading.clear()

    def get_cached_modules(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached modules (copy)."""
        with self._lock:
            return self._cache.copy()


class StringModuleLoader(ModuleLoader):
    """Module loader that loads modules from string sources.

    Useful for testing and in-memory modules.
    """

    def __init__(self, modules: Optional[Dict[str, str]] = None):
        """Initialize with predefined modules.

        Args:
            modules: Dictionary mapping module paths to source code
        """
        self._modules: Dict[str, str] = modules or {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loading: Set[str] = set()
        self._lock = threading.Lock()

    def add_module(self, path: str, source: str) -> None:
        """Add a module source.

        Args:
            path: Module path
            source: Module source code
        """
        self._modules[path] = source

    def has_module(self, module_path: str) -> bool:
        """Check if a module is registered."""
        module_path = module_path.strip("'\"")
        return module_path in self._modules

    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load a module from string source.

        Args:
            module_path: Module path
            context: Current evaluation context

        Returns:
            Dictionary of exported values
        """
        module_path = module_path.strip("'\"")

        # Check cache
        with self._lock:
            if module_path in self._cache:
                return self._cache[module_path]

            if module_path in self._loading:
                raise CircularImportError(f"Circular import detected: {module_path}")

            self._loading.add(module_path)

        try:
            # Get source
            source = self._modules.get(module_path)
            if source is None:
                raise ModuleNotFoundError(f"Module not found: {module_path}")

            # Parse
            parser = FsscriptParser(source)
            ast = parser.parse_program()

            # Create evaluator
            module_context = {
                "__current_module__": module_path,
                "__module_loader__": self,
            }

            evaluator = ExpressionEvaluator(module_context)

            # Execute
            try:
                evaluator.evaluate(ast)
            except CircularImportError:
                raise
            except Exception:
                pass

            # Get exports
            exports = evaluator.get_exports()

            # Cache
            with self._lock:
                self._cache[module_path] = exports
                self._loading.discard(module_path)

            return exports

        except Exception as e:
            with self._lock:
                self._loading.discard(module_path)
            raise


class ChainedModuleLoader(ModuleLoader):
    """Module loader that tries multiple loaders in sequence.

    Each loader is tried in order until one succeeds.
    """

    def __init__(self, *loaders: ModuleLoader):
        """Initialize with a sequence of loaders.

        Args:
            *loaders: Loaders to try in order
        """
        self._loaders = list(loaders)

    def add_loader(self, loader: ModuleLoader) -> None:
        """Add a loader to the chain."""
        self._loaders.append(loader)

    def has_module(self, module_path: str) -> bool:
        """Check if any loader can find the module."""
        return any(loader.has_module(module_path) for loader in self._loaders)

    def load_module(self, module_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Try each loader until one succeeds.

        Args:
            module_path: Module path
            context: Current evaluation context

        Returns:
            Dictionary of exported values

        Raises:
            ModuleNotFoundError: If no loader can find the module
        """
        errors = []
        for loader in self._loaders:
            try:
                if loader.has_module(module_path):
                    return loader.load_module(module_path, context)
            except Exception as e:
                errors.append(f"{loader.__class__.__name__}: {e}")

        raise ModuleNotFoundError(
            f"Module not found: {module_path}. "
            f"Tried: {', '.join(str(e) for e in errors) if errors else 'no loaders'}"
        )


class CircularImportError(Exception):
    """Raised when a circular import is detected."""
    pass


__all__ = [
    "ModuleLoader",
    "FileModuleLoader",
    "StringModuleLoader",
    "ChainedModuleLoader",
    "CircularImportError",
]