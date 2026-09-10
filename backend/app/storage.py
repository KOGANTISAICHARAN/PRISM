from __future__ import annotations

import hashlib
import io
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from .config import settings


class StorageError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_capture_timestamp(data: bytes, content_type: str) -> datetime | None:
    """Best-effort EXIF DateTimeOriginal extraction (images only)."""
    if not content_type.startswith("image/"):
        return None
    try:
        from PIL import Image, ExifTags

        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
            if not exif:
                return None
            tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            raw = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
            if isinstance(raw, str):
                return datetime.strptime(raw.strip(), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


class Storage:
    """Object storage abstraction: local disk (default) or Supabase Storage."""

    def __init__(self) -> None:
        self.backend = settings.storage_backend
        self.root = Path(settings.local_storage_dir)
        if self.backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, file_name: str, content_type: str, prefix: str = "evidence") -> tuple[str, str]:
        """Store bytes immutably. Returns (storage_key, public_or_api_url)."""
        ext = Path(file_name).suffix or mimetypes.guess_extension(content_type) or ""
        key = f"{prefix}/{datetime.utcnow():%Y/%m}/{uuid.uuid4().hex}{ext}"

        if self.backend == "supabase":
            if not (settings.supabase_url and settings.supabase_service_role_key):
                raise StorageError("Supabase storage selected but credentials are missing")
            url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{key}"
            resp = httpx.post(
                url,
                content=data,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": content_type or "application/octet-stream",
                    "x-upsert": "false",  # never overwrite original evidence
                },
                timeout=60,
            )
            if resp.status_code >= 400:
                raise StorageError(f"Supabase upload failed: {resp.status_code} {resp.text[:200]}")
            return key, f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{settings.supabase_storage_bucket}/{key}"

        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():  # never overwrite
            raise StorageError("Storage key collision")
        path.write_bytes(data)
        return key, f"/evidence/file/{key}"

    def read(self, key: str) -> bytes:
        if self.backend == "supabase":
            url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{key}"
            resp = httpx.get(url, headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"}, timeout=60)
            resp.raise_for_status()
            return resp.content
        path = self.root / key
        if not path.exists():
            raise StorageError("Evidence file not found")
        return path.read_bytes()


storage = Storage()
