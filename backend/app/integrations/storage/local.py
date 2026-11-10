import os
import uuid
import shutil
from pathlib import Path
from typing import BinaryIO, Optional
from backend.app.core.config import settings
from backend.app.integrations.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider with path-traversal prevention."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or settings.UPLOAD_DIR).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        safe_name = Path(filename).name
        # Prepend unique uuid to prevent collision
        unique_prefix = uuid.uuid4().hex[:12]
        return f"{unique_prefix}_{safe_name}"

    async def save_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str,
        subfolder: str = ""
    ) -> str:
        safe_subfolder = Path(subfolder).name if subfolder else ""
        target_dir = (self.root_dir / safe_subfolder).resolve()

        # Path traversal prevention
        if not str(target_dir).startswith(str(self.root_dir)):
            raise ValueError("Invalid subfolder: path traversal detected.")

        target_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = self._sanitize_filename(filename)
        dest_path = target_dir / safe_filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)

        # Return relative path for database storage
        if safe_subfolder:
            return f"{safe_subfolder}/{safe_filename}"
        return safe_filename

    async def delete_file(self, file_path: str) -> bool:
        target = (self.root_dir / file_path).resolve()
        if not str(target).startswith(str(self.root_dir)):
            return False
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False

    def get_public_url(self, file_path: str) -> str:
        clean_path = file_path.replace("\\", "/").lstrip("/")
        return f"/uploads/{clean_path}"


storage = LocalStorageProvider()
