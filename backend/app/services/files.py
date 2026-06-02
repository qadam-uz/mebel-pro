"""File metadata and object-storage seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import boto3

from app.core.config import settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str


class FileStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> StoredObject: ...

    def open(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3FileStorage:
    def __init__(self) -> None:
        self._bucket = settings.MINIO_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT_URL,
            region_name=settings.MINIO_REGION,
            aws_access_key_id=settings.MINIO_ACCESS_KEY_ID,
            aws_secret_access_key=settings.MINIO_SECRET_ACCESS_KEY,
            use_ssl=settings.MINIO_USE_SSL,
        )

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(key=key, size_bytes=len(content), content_type=content_type)

    def open(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        data = body.read()
        return bytes(data)

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


class InMemoryFileStorage:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.contents: dict[str, bytes] = {}

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        obj = StoredObject(key=key, size_bytes=len(content), content_type=content_type)
        self.objects[key] = obj
        self.contents[key] = content
        return obj

    def open(self, key: str) -> bytes:
        return self.contents[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.contents.pop(key, None)
