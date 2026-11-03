"""S3 / MinIO Object Storage integration and retention manager for Type C batch carrier files."""

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("type_c_storage")


class S3StorageManager:
    """Manages S3/MinIO bucket lifecycle, uploads, retention policies, and presigned access."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str | None = None,
        region_name: str = "us-east-1",
    ) -> None:
        self.endpoint_url = endpoint_url or os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "cargaexpress_admin"))
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "cargaexpress_minio_secret_123"))
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "type-c-carriers")
        self.region_name = region_name

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_bucket(self) -> None:
        """Create bucket if it does not already exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info("Bucket '%s' exists and is accessible.", self.bucket_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                logger.info("Bucket '%s' not found. Creating...", self.bucket_name)
                try:
                    if self.region_name and self.region_name != "us-east-1":
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region_name},
                        )
                    else:
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info("Bucket '%s' created successfully.", self.bucket_name)
                except ClientError as create_err:
                    logger.error("Failed to create bucket '%s': %s", self.bucket_name, create_err)
                    raise
            else:
                logger.warning("Could not head bucket '%s' (%s). Will attempt operations.", self.bucket_name, exc)

    def upload_file(
        self,
        local_path: Path | str,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        """Upload a file to the S3/MinIO bucket and return the remote object key."""
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(f"File to upload not found: {path}")

        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        else:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                extra_args["ContentType"] = "text/csv; charset=utf-8"
            elif suffix == ".xlsx":
                extra_args["ContentType"] = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        logger.info("Uploading '%s' to 's3://%s/%s'...", path.name, self.bucket_name, object_key)
        self.s3_client.upload_file(
            Filename=str(path),
            Bucket=self.bucket_name,
            Key=object_key,
            ExtraArgs=extra_args if extra_args else None,
        )
        return object_key

    def list_objects(self, prefix: str = "") -> list[dict[str, Any]]:
        """List objects in bucket matching prefix."""
        items: list[dict[str, Any]] = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                items.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                })
        return items

    def cleanup_retention(self, retention_days: int) -> list[str]:
        """Purge objects older than retention_days to prevent storage costs and bloat."""
        if retention_days <= 0:
            logger.info("Retention days is <= 0; skipping cleanup.")
            return []

        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        logger.info("Running retention purge: deleting objects older than %s (%d days)...", cutoff_date.isoformat(), retention_days)

        deleted_keys: list[str] = []
        objects = self.list_objects()
        for obj in objects:
            last_mod = obj["last_modified"]
            if last_mod < cutoff_date:
                key = obj["key"]
                logger.info("Purging expired object '%s' (LastModified: %s)", key, last_mod.isoformat())
                try:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                    deleted_keys.append(key)
                except ClientError as err:
                    logger.error("Failed to delete expired object '%s': %s", key, err)

        logger.info("Retention purge completed. Total purged: %d objects.", len(deleted_keys))
        return deleted_keys

    def generate_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Generate presigned download URL for secure direct client extraction."""
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": object_key},
            ExpiresIn=expires_in,
        )
