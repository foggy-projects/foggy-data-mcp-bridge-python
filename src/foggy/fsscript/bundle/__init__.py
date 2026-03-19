"""Bundle system for FSScript module loading.

Bundles are the unit of modularity in FSScript, similar to OSGi bundles.
Each bundle can contain scripts, resources, and provide services.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime


class BundleState(str, Enum):
    """Bundle lifecycle state."""

    UNINSTALLED = "uninstalled"
    INSTALLED = "installed"
    RESOLVED = "resolved"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"


class BundleResource(BaseModel):
    """Resource within a bundle.

    Represents a file or data resource packaged within a bundle.
    """

    # Identity
    name: str = Field(..., description="Resource name")
    path: str = Field(..., description="Resource path within bundle")

    # Content
    content_type: Optional[str] = Field(default=None, description="MIME type")
    content: Optional[bytes] = Field(default=None, description="Binary content")
    text_content: Optional[str] = Field(default=None, description="Text content")

    # Metadata
    size: Optional[int] = Field(default=None, description="Size in bytes")
    last_modified: Optional[datetime] = Field(default=None, description="Last modification time")

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def get_text(self) -> Optional[str]:
        """Get text content, decoding if necessary."""
        if self.text_content:
            return self.text_content
        if self.content:
            return self.content.decode("utf-8")
        return None

    def get_bytes(self) -> Optional[bytes]:
        """Get binary content."""
        if self.content:
            return self.content
        if self.text_content:
            return self.text_content.encode("utf-8")
        return None


class Bundle(ABC):
    """Abstract bundle interface.

    A bundle is a modular unit that can be loaded, started, and stopped.
    Bundles can contain scripts, resources, and provide services.
    """

    @property
    @abstractmethod
    def bundle_id(self) -> str:
        """Unique identifier for this bundle."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable bundle name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Bundle version string."""
        pass

    @property
    @abstractmethod
    def state(self) -> BundleState:
        """Current bundle state."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the bundle."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the bundle."""
        pass

    @abstractmethod
    def get_resource(self, path: str) -> Optional[BundleResource]:
        """Get a resource by path.

        Args:
            path: Resource path within bundle

        Returns:
            BundleResource or None if not found
        """
        pass

    @abstractmethod
    def get_resources(self) -> List[BundleResource]:
        """Get all resources in this bundle."""
        pass

    @abstractmethod
    def get_entry_point(self) -> Optional[str]:
        """Get the entry point script name."""
        pass


class BundleImpl(Bundle, BaseModel):
    """Concrete bundle implementation.

    Default implementation of the Bundle interface.
    """

    # Identity
    _bundle_id: str = ""
    _name: str = ""
    _version: str = "1.0.0"
    _state: BundleState = BundleState.INSTALLED

    # Content
    resources: Dict[str, BundleResource] = Field(default_factory=dict)
    entry_point: Optional[str] = Field(default=None, description="Entry point script name")

    # Dependencies
    dependencies: List[str] = Field(default_factory=list, description="Required bundle IDs")

    # Metadata
    description: Optional[str] = Field(default=None, description="Bundle description")
    author: Optional[str] = Field(default=None, description="Bundle author")
    created_at: Optional[datetime] = Field(default=None, description="Creation time")

    # Lifecycle callbacks
    on_start: Optional[Callable[[], None]] = Field(default=None, description="Start callback")
    on_stop: Optional[Callable[[], None]] = Field(default=None, description="Stop callback")

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def __init__(self, bundle_id: str, name: str = "", version: str = "1.0.0", **data):
        super().__init__(**data)
        self._bundle_id = bundle_id
        self._name = name or bundle_id
        self._version = version
        self._state = BundleState.INSTALLED

    @property
    def bundle_id(self) -> str:
        return self._bundle_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def state(self) -> BundleState:
        return self._state

    def start(self) -> None:
        """Start the bundle."""
        if self._state == BundleState.ACTIVE:
            return

        self._state = BundleState.STARTING

        try:
            if self.on_start:
                self.on_start()
            self._state = BundleState.ACTIVE
        except Exception:
            self._state = BundleState.RESOLVED
            raise

    def stop(self) -> None:
        """Stop the bundle."""
        if self._state != BundleState.ACTIVE:
            return

        self._state = BundleState.STOPPING

        try:
            if self.on_stop:
                self.on_stop()
        finally:
            self._state = BundleState.RESOLVED

    def get_resource(self, path: str) -> Optional[BundleResource]:
        """Get a resource by path."""
        return self.resources.get(path)

    def get_resources(self) -> List[BundleResource]:
        """Get all resources."""
        return list(self.resources.values())

    def get_entry_point(self) -> Optional[str]:
        """Get the entry point script name."""
        return self.entry_point

    def add_resource(self, resource: BundleResource) -> "BundleImpl":
        """Add a resource to this bundle.

        Args:
            resource: Resource to add

        Returns:
            Self for chaining
        """
        self.resources[resource.path] = resource
        return self

    def remove_resource(self, path: str) -> Optional[BundleResource]:
        """Remove a resource by path.

        Args:
            path: Resource path

        Returns:
            Removed resource or None
        """
        return self.resources.pop(path, None)


class BundleLoader(ABC):
    """Abstract bundle loader interface.

    Bundle loaders are responsible for loading bundles from
    different sources (files, directories, URLs, etc.).
    """

    @abstractmethod
    def can_load(self, source: str) -> bool:
        """Check if this loader can load from the given source.

        Args:
            source: Source identifier (path, URL, etc.)

        Returns:
            True if this loader can handle the source
        """
        pass

    @abstractmethod
    def load(self, source: str) -> Bundle:
        """Load a bundle from the given source.

        Args:
            source: Source identifier

        Returns:
            Loaded bundle

        Raises:
            BundleLoadError: If loading fails
        """
        pass


class FileBundleLoader(BundleLoader):
    """Loader for bundles from file system directories."""

    def can_load(self, source: str) -> bool:
        """Check if source is a valid directory."""
        path = Path(source)
        return path.exists() and path.is_dir()

    def load(self, source: str) -> Bundle:
        """Load a bundle from a directory.

        Args:
            source: Directory path

        Returns:
            Loaded bundle
        """
        path = Path(source)
        bundle_id = path.name

        bundle = BundleImpl(bundle_id=bundle_id)

        # Load resources from directory
        for file_path in path.rglob("*"):
            if file_path.is_file():
                relative_path = str(file_path.relative_to(path))
                resource = BundleResource(
                    name=file_path.name,
                    path=relative_path,
                )

                # Load content based on file type
                try:
                    if file_path.suffix in (".json", ".js", ".ts", ".py", ".txt", ".md"):
                        resource.text_content = file_path.read_text(encoding="utf-8")
                    else:
                        resource.content = file_path.read_bytes()
                except Exception:
                    pass  # Skip files that can't be read

                bundle.add_resource(resource)

        return bundle


class BundleLoadError(Exception):
    """Exception raised when bundle loading fails."""

    def __init__(self, message: str, source: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.source = source
        self.cause = cause


class BundleContext(BaseModel):
    """Execution context for a bundle.

    Provides access to bundle resources, services, and other bundles.
    """

    bundle: BundleImpl
    properties: Dict[str, Any] = Field(default_factory=dict)
    services: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a context property."""
        return self.properties.get(key, default)

    def set_property(self, key: str, value: Any) -> None:
        """Set a context property."""
        self.properties[key] = value

    def register_service(self, name: str, service: Any) -> None:
        """Register a service."""
        self.services[name] = service

    def get_service(self, name: str) -> Optional[Any]:
        """Get a registered service."""
        return self.services.get(name)


class SystemBundlesContext(BaseModel):
    """System-wide context managing all bundles.

    Provides bundle lifecycle management and inter-bundle communication.
    """

    bundles: Dict[str, BundleImpl] = Field(default_factory=dict)
    bundle_contexts: Dict[str, BundleContext] = Field(default_factory=dict)
    loaders: List[BundleLoader] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True,
    }

    def __init__(self, **data):
        super().__init__(**data)
        # Register default loaders
        self.loaders.append(FileBundleLoader())

    def install_bundle(self, source: str) -> BundleImpl:
        """Install a bundle from source.

        Args:
            source: Bundle source (path, URL, etc.)

        Returns:
            Installed bundle

        Raises:
            BundleLoadError: If installation fails
        """
        for loader in self.loaders:
            if loader.can_load(source):
                bundle = loader.load(source)
                self.bundles[bundle.bundle_id] = bundle
                self.bundle_contexts[bundle.bundle_id] = BundleContext(bundle=bundle)
                return bundle

        raise BundleLoadError(f"No loader found for source: {source}", source=source)

    def uninstall_bundle(self, bundle_id: str) -> bool:
        """Uninstall a bundle.

        Args:
            bundle_id: Bundle ID to uninstall

        Returns:
            True if bundle was uninstalled
        """
        if bundle_id in self.bundles:
            bundle = self.bundles[bundle_id]
            if bundle.state == BundleState.ACTIVE:
                bundle.stop()
            del self.bundles[bundle_id]
            self.bundle_contexts.pop(bundle_id, None)
            return True
        return False

    def start_bundle(self, bundle_id: str) -> None:
        """Start a bundle."""
        if bundle_id in self.bundles:
            self.bundles[bundle_id].start()

    def stop_bundle(self, bundle_id: str) -> None:
        """Stop a bundle."""
        if bundle_id in self.bundles:
            self.bundles[bundle_id].stop()

    def get_bundle(self, bundle_id: str) -> Optional[BundleImpl]:
        """Get a bundle by ID."""
        return self.bundles.get(bundle_id)

    def get_active_bundles(self) -> List[BundleImpl]:
        """Get all active bundles."""
        return [b for b in self.bundles.values() if b.state == BundleState.ACTIVE]