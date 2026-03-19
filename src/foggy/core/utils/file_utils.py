"""File utilities for Foggy Framework."""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Union


class FileUtils:
    """File utility functions."""

    @staticmethod
    def read_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
        """Read file content.

        Args:
            path: File path
            encoding: File encoding

        Returns:
            File content as string
        """
        path = Path(path)
        return path.read_text(encoding=encoding)

    @staticmethod
    def read_bytes(path: Union[str, Path]) -> bytes:
        """Read file as bytes.

        Args:
            path: File path

        Returns:
            File content as bytes
        """
        path = Path(path)
        return path.read_bytes()

    @staticmethod
    def write_file(
        path: Union[str, Path], content: Union[str, bytes], encoding: str = "utf-8"
    ) -> None:
        """Write content to file.

        Args:
            path: File path
            content: Content to write
            encoding: File encoding (for string content)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding=encoding)

    @staticmethod
    def append_file(path: Union[str, Path], content: str, encoding: str = "utf-8") -> None:
        """Append content to file.

        Args:
            path: File path
            content: Content to append
            encoding: File encoding
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(content)

    @staticmethod
    def delete_file(path: Union[str, Path]) -> bool:
        """Delete a file.

        Args:
            path: File path

        Returns:
            True if file was deleted, False if it didn't exist
        """
        path = Path(path)
        if path.exists():
            path.unlink()
            return True
        return False

    @staticmethod
    def delete_directory(path: Union[str, Path]) -> bool:
        """Delete a directory and all its contents.

        Args:
            path: Directory path

        Returns:
            True if directory was deleted, False if it didn't exist
        """
        path = Path(path)
        if path.exists():
            shutil.rmtree(path)
            return True
        return False

    @staticmethod
    def exists(path: Union[str, Path]) -> bool:
        """Check if path exists."""
        return Path(path).exists()

    @staticmethod
    def is_file(path: Union[str, Path]) -> bool:
        """Check if path is a file."""
        return Path(path).is_file()

    @staticmethod
    def is_directory(path: Union[str, Path]) -> bool:
        """Check if path is a directory."""
        return Path(path).is_dir()

    @staticmethod
    def create_directory(path: Union[str, Path]) -> Path:
        """Create directory (and parents if needed).

        Args:
            path: Directory path

        Returns:
            Path object
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def list_files(
        path: Union[str, Path], pattern: str = "*", recursive: bool = False
    ) -> List[Path]:
        """List files in directory.

        Args:
            path: Directory path
            pattern: Glob pattern
            recursive: Whether to search recursively

        Returns:
            List of file paths
        """
        path = Path(path)
        if recursive:
            return list(path.rglob(pattern))
        return list(path.glob(pattern))

    @staticmethod
    def get_extension(path: Union[str, Path]) -> str:
        """Get file extension (without dot).

        Args:
            path: File path

        Returns:
            File extension (lowercase)
        """
        return Path(path).suffix.lower().lstrip(".")

    @staticmethod
    def get_filename(path: Union[str, Path]) -> str:
        """Get filename without extension.

        Args:
            path: File path

        Returns:
            Filename without extension
        """
        return Path(path).stem

    @staticmethod
    def get_basename(path: Union[str, Path]) -> str:
        """Get filename with extension.

        Args:
            path: File path

        Returns:
            Filename with extension
        """
        return Path(path).name

    @staticmethod
    def get_parent(path: Union[str, Path]) -> Path:
        """Get parent directory.

        Args:
            path: File path

        Returns:
            Parent directory path
        """
        return Path(path).parent

    @staticmethod
    def get_size(path: Union[str, Path]) -> int:
        """Get file size in bytes.

        Args:
            path: File path

        Returns:
            File size in bytes
        """
        return Path(path).stat().st_size

    @staticmethod
    def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """Copy file.

        Args:
            src: Source file path
            dst: Destination file path

        Returns:
            Destination path
        """
        src = Path(src)
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    @staticmethod
    def move_file(src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """Move file.

        Args:
            src: Source file path
            dst: Destination file path

        Returns:
            Destination path
        """
        src = Path(src)
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return dst

    @staticmethod
    def join(*paths: Union[str, Path]) -> Path:
        """Join path components.

        Args:
            *paths: Path components

        Returns:
            Joined path
        """
        result = Path(paths[0])
        for p in paths[1:]:
            result = result / p
        return result