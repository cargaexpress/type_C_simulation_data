"""Tests for Type C MinIO/S3 Storage and Periodic Scheduler with Retention Purging."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from simulators.type_c.scheduler import run_batch_cycle
from simulators.type_c.storage import S3StorageManager


def test_storage_manager_init():
    storage = S3StorageManager(
        endpoint_url="http://mock-minio:9000",
        access_key="test_user",
        secret_key="test_pass",
        bucket_name="test-bucket",
    )
    assert storage.endpoint_url == "http://mock-minio:9000"
    assert storage.bucket_name == "test-bucket"


def test_storage_ensure_bucket_creates_when_missing():
    storage = S3StorageManager(bucket_name="test-bucket")
    storage.s3_client = MagicMock()
    # Mock head_bucket throwing NoSuchBucket error
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    from botocore.exceptions import ClientError
    storage.s3_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")

    storage.ensure_bucket()
    storage.s3_client.create_bucket.assert_called_once_with(Bucket="test-bucket")


def test_storage_upload_file():
    storage = S3StorageManager(bucket_name="test-bucket")
    storage.s3_client = MagicMock()

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"header1,header2\nval1,val2\n")
        f_path = Path(f.name)

    try:
        remote_key = storage.upload_file(f_path, "carrier_1/test.csv")
        assert remote_key == "carrier_1/test.csv"
        storage.s3_client.upload_file.assert_called_once()
    finally:
        f_path.unlink(missing_ok=True)


def test_storage_cleanup_retention():
    storage = S3StorageManager(bucket_name="test-bucket")
    storage.s3_client = MagicMock()

    old_date = datetime.now(UTC) - timedelta(days=5)
    new_date = datetime.now(UTC) - timedelta(days=1)

    # Mock list_objects
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Contents": [
                {"Key": "old_file.csv", "Size": 100, "LastModified": old_date},
                {"Key": "new_file.csv", "Size": 200, "LastModified": new_date},
            ]
        }
    ]
    storage.s3_client.get_paginator.return_value = mock_paginator

    deleted = storage.cleanup_retention(retention_days=3)
    assert deleted == ["old_file.csv"]
    storage.s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="old_file.csv")


def test_run_batch_cycle():
    mock_storage = MagicMock(spec=S3StorageManager)
    mock_storage.bucket_name = "type-c-carriers"
    mock_storage.cleanup_retention.return_value = ["purged_1.csv"]
    mock_storage.generate_presigned_url.return_value = "http://minio:9000/presigned-url"

    manifest = run_batch_cycle(
        storage=mock_storage,
        rows_per_carrier=10,
        error_rate=0.05,
        seed=42,
        retention_days=3,
    )

    assert manifest["carriers_count"] == 3
    assert len(manifest["batches"]) == 3
    assert manifest["retention_days"] == 3
    assert manifest["purged_old_files_count"] == 1

    carrier_ids = [b["carrier_id"] for b in manifest["batches"]]
    assert carrier_ids == [1, 2, 3]

    formats = [b["format"] for b in manifest["batches"]]
    assert formats == ["csv", "xlsx", "csv"]

    # Verify upload was called for files + manifests
    assert mock_storage.upload_file.call_count >= 8
