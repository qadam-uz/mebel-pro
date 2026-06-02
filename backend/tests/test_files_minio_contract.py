import os
import uuid

import pytest
from app.services.files import S3FileStorage

pytestmark = pytest.mark.skipif(
    os.environ.get("MINIO_CONTRACT") != "1",
    reason="set MINIO_CONTRACT=1 with local MinIO running",
)


def test_s3_file_storage_round_trips_against_minio() -> None:
    storage = S3FileStorage()
    key = f"contract/{uuid.uuid4()}.txt"

    stored = storage.put(key, b"minio-contract", "text/plain")
    try:
        assert stored.key == key
        assert stored.size_bytes == len(b"minio-contract")
        assert storage.open(key) == b"minio-contract"
    finally:
        storage.delete(key)
