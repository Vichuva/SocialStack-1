import os
import uuid
from pathlib import Path
from typing import Protocol

from socialstack.utils.errors import StorageError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class StorageBackend(Protocol):
    async def save(self, content: bytes, filename: str, content_type: str) -> str:
        """Save bytes and return a publicly accessible URL."""
        ...

    async def delete(self, url: str) -> None:
        ...


class LocalStorage:
    def __init__(self, base_path: str, base_url: str):
        self.base_path = Path(base_path)
        self.base_url = base_url.rstrip("/")
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, filename: str, content_type: str) -> str:
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = self.base_path / unique_name
        file_path.write_bytes(content)
        logger.info("stored_file", path=str(file_path), size=len(content))
        return f"{self.base_url}/{unique_name}"

    async def delete(self, url: str) -> None:
        filename = url.split("/")[-1]
        file_path = self.base_path / filename
        if file_path.exists():
            file_path.unlink()


class S3Storage:
    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str):
        import boto3
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def save(self, content: bytes, filename: str, content_type: str) -> str:
        import asyncio
        key = f"media/{uuid.uuid4().hex}_{filename}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                ACL="public-read",
            ),
        )
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"

    async def delete(self, url: str) -> None:
        import asyncio
        key = "/".join(url.split("/")[3:])
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.delete_object(Bucket=self.bucket, Key=key))


def get_storage() -> StorageBackend:
    from socialstack.config import get_settings
    settings = get_settings()

    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_path, settings.local_storage_base_url)
    elif settings.storage_backend == "s3":
        return S3Storage(
            settings.s3_bucket,
            settings.s3_region,
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
        )
    else:
        raise StorageError(f"Unsupported storage backend: {settings.storage_backend}")
