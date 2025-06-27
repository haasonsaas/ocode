"""
Atomic file operations for improved resiliency.

This module provides atomic operations for file writing to prevent
data loss and corruption during write operations.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, IO, Optional, Tuple, Union


class AtomicFileWriter:
    """Context manager for atomic file writes.

    Writes to a temporary file and atomically replaces the target file
    only after successful completion. This prevents partial writes and
    data corruption.
    """

    def __init__(
        self,
        target_path: Union[str, Path],
        mode: str = "w",
        encoding: Optional[str] = "utf-8",
        backup: bool = True,
        sync: bool = True,
    ):
        """Initialize atomic file writer.

        Args:
            target_path: Path to the target file
            mode: File open mode (must be write mode)
            encoding: Text encoding (None for binary mode)
            backup: Whether to create a backup of existing file
            sync: Whether to sync to disk before rename
        """
        if "r" in mode:
            raise ValueError("AtomicFileWriter only supports write modes")

        self.target_path = Path(target_path)
        self.mode = mode
        self.encoding = encoding
        self.backup = backup
        self.sync = sync
        self.temp_file: Optional[IO[Any]] = None
        self.temp_path: Optional[Path] = None
        self.backup_path: Optional[Path] = None
        self._closed = False

    def __enter__(self) -> IO[Any]:
        """Enter context manager, create temporary file."""
        # Create temporary file in same directory as target
        # This ensures atomic rename on same filesystem
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.target_path.parent,
            prefix=f".{self.target_path.name}.",
            suffix=".tmp",
        )

        self.temp_path = Path(temp_path)

        # Open the temporary file with requested mode
        if "b" in self.mode:
            self.temp_file = os.fdopen(temp_fd, self.mode)
        else:
            os.close(temp_fd)  # Close the file descriptor
            self.temp_file = open(self.temp_path, self.mode, encoding=self.encoding)

        # Ensure attributes are set for type checker
        assert self.temp_file is not None
        assert self.temp_path is not None
        
        return self.temp_file

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, handle atomic replacement."""
        if self._closed:
            return

        self._closed = True

        # Close temporary file
        if self.temp_file and not self.temp_file.closed:
            if self.sync and hasattr(self.temp_file, "fileno"):
                try:
                    # Sync to disk for durability
                    self.temp_file.flush()
                    os.fsync(self.temp_file.fileno())
                except (OSError, ValueError):
                    pass  # File might be closed or not support sync

            self.temp_file.close()

        # If there was an exception, clean up and propagate
        if exc_type is not None:
            try:
                if self.temp_path and self.temp_path.exists():
                    self.temp_path.unlink()
            except Exception:
                pass  # Best effort cleanup
            return

        # No exception, perform atomic replacement
        # temp_path should be set by __enter__
        assert self.temp_path is not None
        
        try:
            # Create backup if requested and target exists
            if self.backup and self.target_path.exists():
                self.backup_path = self.target_path.with_suffix(
                    self.target_path.suffix + ".bak"
                )
                # Use hard link for instant backup (copy-on-write)
                try:
                    if self.backup_path.exists():
                        self.backup_path.unlink()
                    os.link(str(self.target_path), str(self.backup_path))
                except (OSError, NotImplementedError):
                    # Fall back to copy if hard links not supported
                    import shutil

                    shutil.copy2(str(self.target_path), str(self.backup_path))

            # Preserve permissions if target exists
            if self.target_path.exists():
                try:
                    stat_info = self.target_path.stat()
                    os.chmod(self.temp_path, stat_info.st_mode)
                    # Try to preserve ownership (may fail without privileges)
                    try:
                        os.chown(self.temp_path, stat_info.st_uid, stat_info.st_gid)
                    except (OSError, AttributeError):
                        pass  # Not critical, ignore
                except Exception:
                    pass  # Best effort

            # Atomic rename
            # On POSIX, rename is atomic. On Windows, we need to remove target first
            if os.name == "nt" and self.target_path.exists():
                # Windows doesn't support atomic rename over existing file
                # This creates a small window of vulnerability
                self.target_path.unlink()

            os.rename(str(self.temp_path), str(self.target_path))

            # Clean up backup if everything succeeded
            if self.backup_path and self.backup_path.exists():
                try:
                    # Keep backup for safety, but could be configured
                    pass  # self.backup_path.unlink()
                except Exception:
                    pass

        except Exception as e:
            # Try to clean up temporary file
            try:
                if self.temp_path and self.temp_path.exists():
                    self.temp_path.unlink()
            except Exception:
                pass
            raise e

    def abort(self) -> None:
        """Abort the write operation and clean up."""
        if not self._closed:
            self._closed = True
            if self.temp_file and not self.temp_file.closed:
                self.temp_file.close()
            if self.temp_path and self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass


def atomic_write(
    path: Union[str, Path],
    content: Union[str, bytes],
    encoding: Optional[str] = "utf-8",
    backup: bool = True,
    sync: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Atomically write content to a file.

    Args:
        path: Target file path
        content: Content to write
        encoding: Text encoding (None for binary)
        backup: Whether to create backup of existing file
        sync: Whether to sync to disk before rename

    Returns:
        Tuple of (success, error_message)
    """
    try:
        mode = "wb" if isinstance(content, bytes) else "w"
        if isinstance(content, bytes):
            encoding = None

        with AtomicFileWriter(
            path, mode=mode, encoding=encoding, backup=backup, sync=sync
        ) as f:
            f.write(content)

        return True, None

    except Exception as e:
        return False, str(e)


def safe_file_update(
    path: Union[str, Path], 
    update_func: Callable[[str], str], 
    encoding: str = "utf-8", 
    backup: bool = True
) -> Tuple[bool, Optional[str]]:
    """Safely update a file by reading, transforming, and atomically writing.

    Args:
        path: File to update
        update_func: Function that takes current content and returns new content
        encoding: Text encoding
        backup: Whether to create backup

    Returns:
        Tuple of (success, error_message)
    """
    try:
        path = Path(path)

        # Read current content
        if path.exists():
            with open(path, "r", encoding=encoding) as f:
                current_content = f.read()
        else:
            current_content = ""

        # Transform content
        new_content = update_func(current_content)

        # Atomically write new content
        return atomic_write(path, new_content, encoding=encoding, backup=backup)

    except Exception as e:
        return False, str(e)
