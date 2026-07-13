from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


def document_object_key(tenant_id: str, filename: str) -> str:
    tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:20]
    suffix = Path(filename).suffix.lower()[:12]
    return f"tenants/{tenant_hash}/documents/{uuid4().hex}{suffix}"


def _safe_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Object key is invalid")
    return path


class LocalObjectStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        target = self.root.joinpath(*_safe_key(key).parts).resolve()
        if self.root not in target.parents:
            raise ValueError("Object key leaves the storage root")
        return target

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3ObjectStorage:
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - production dependency
            raise RuntimeError("boto3 is required for S3 object storage") from exc
        self.bucket = os.environ["S3_BUCKET"]
        self.kms_key_id = os.getenv("S3_KMS_KEY_ID")
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            region_name=os.getenv("S3_REGION") or None,
        )

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        _safe_key(key)
        kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type or "application/octet-stream",
            "ServerSideEncryption": "aws:kms" if self.kms_key_id else "AES256",
        }
        if self.kms_key_id:
            kwargs["SSEKMSKeyId"] = self.kms_key_id
        self.client.put_object(**kwargs)

    def get(self, key: str) -> bytes:
        _safe_key(key)
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        _safe_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)


def build_object_storage() -> ObjectStorage:
    backend = os.getenv("OBJECT_STORAGE_BACKEND", "local").lower()
    if backend == "s3":
        return S3ObjectStorage()
    if backend == "local" and os.getenv("APP_ENV", "development") != "production":
        return LocalObjectStorage(os.getenv("LOCAL_OBJECT_STORAGE_PATH", "./data/uploads"))
    raise RuntimeError("Production requires OBJECT_STORAGE_BACKEND=s3")


class MalwareScanner:
    def __init__(self) -> None:
        self.command = os.getenv("CLAMAV_COMMAND", "clamscan")

    def scan(self, data: bytes) -> None:
        executable = shutil.which(self.command)
        required = os.getenv("APP_ENV", "development") == "production" or os.getenv("CLAMAV_REQUIRED") == "1"
        if not executable:
            if required:
                raise RuntimeError("Malware scanner is required but unavailable")
            return
        result = subprocess.run(
            [executable, "--no-summary", "-"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        if result.returncode == 1:
            raise ValueError("Malware detected in uploaded document")
        if result.returncode not in {0}:
            raise RuntimeError("Malware scanner failed")

