from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class StorageProvider(ABC):
    """Abstract interface for local or cloud object storage."""

    @abstractmethod
    async def save_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str,
        subfolder: str = ""
    ) -> str:
        """Save a file and return its accessible relative path or URI."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file by its stored path."""
        pass

    @abstractmethod
    def get_public_url(self, file_path: str) -> str:
        """Return the URL to access the file."""
        pass
