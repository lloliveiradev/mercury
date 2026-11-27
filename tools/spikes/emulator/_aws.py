import boto3
import dotenv
import os
import sys
import time

from pathlib import Path
from typing import Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/spikes, for _utils

from _utils import _size, _duration

dotenv.load_dotenv()

BUCKET = "mercury-data"
AWS_EMULATOR_STR = "AWS Emulator"
SEAWEEDFS_STR = "SeaweedFS"
S3_SOURCES = [AWS_EMULATOR_STR, SEAWEEDFS_STR]

type S3Source = Literal["AWS Emulator", "SeaweedFS"]


def get_s3_access(source: S3Source, host: Optional[str] = None) -> dict:
    access_key = None
    secret_key = None
    if source == AWS_EMULATOR_STR:
        if not os.getenv("AWS_SHARED_CREDENTIALS_FILE"):
            raise Exception("AWS_SHARED_CREDENTIALS_FILE env var is not set")
        if not os.getenv("AWS_ENDPOINT_URL"):
            raise Exception("AWS_ENDPOINT_URL env var is not set")
        if not os.path.exists(os.getenv("AWS_SHARED_CREDENTIALS_FILE")):
            raise Exception(
                f"AWS_SHARED_CREDENTIALS_FILE does not exist: {os.getenv('AWS_SHARED_CREDENTIALS_FILE')}"
            )
        with open(os.getenv("AWS_SHARED_CREDENTIALS_FILE"), "r") as f:
            for line in f:
                if line.startswith("aws_access_key_id"):
                    access_key = line.split("=")[1].strip()
                if line.startswith("aws_secret_access_key"):
                    secret_key = line.split("=")[1].strip()
        return {
            "url": os.getenv("AWS_ENDPOINT_URL"),
            "access_key": access_key,
            "secret_key": secret_key,
        }
    elif source == SEAWEEDFS_STR:
        if not host and not os.getenv("SEAWEEDFS_S3_HOST"):
            raise Exception("SEAWEEDFS_S3_HOST env var is not set")
        if not os.getenv("SEAWEEDFS_S3_PORT"):
            raise Exception("SEAWEEDFS_S3_PORT env var is not set")
        if not os.getenv("SEAWEEDFS_ACCESS_KEY"):
            raise Exception("SEAWEEDFS_ACCESS_KEY env var is not set")
        if not os.getenv("SEAWEEDFS_SECRET_KEY"):
            raise Exception("SEAWEEDFS_SECRET_KEY env var is not set")
        return {
            "url": f"http://{host or os.getenv('SEAWEEDFS_S3_HOST')}:{os.getenv('SEAWEEDFS_S3_PORT')}",
            "access_key": os.getenv("SEAWEEDFS_ACCESS_KEY"),
            "secret_key": os.getenv("SEAWEEDFS_SECRET_KEY"),
        }
    else:
        raise ValueError(f"Invalid S3 source: {source}")


def get_s3_client(source: S3Source) -> boto3.client:
    access = get_s3_access(source)
    if source == AWS_EMULATOR_STR:
        return boto3.client("s3")
    elif source == SEAWEEDFS_STR:
        return boto3.client(
            "s3",
            endpoint_url=access["url"],
            aws_access_key_id=access["access_key"],
            aws_secret_access_key=access["secret_key"],
        )

    else:
        raise ValueError(f"Invalid S3 source: {source}")


def _s3_get_bucket(
    bucket: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> Optional[dict]:
    try:
        if not client:
            client = get_s3_client(source)
        head = client.head_bucket(Bucket=bucket)
        return head
    except Exception:
        # head_bucket raises for a bucket that does not exist yet.
        return None


def _s3_create_bucket(
    bucket: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> None:
    try:
        if not client:
            client = get_s3_client(source)
        head = _s3_get_bucket(bucket, source, client)
        if head is not None:
            return
        client.create_bucket(Bucket=bucket)
    except Exception as e:
        raise Exception(f"ERROR: Error creating bucket on {source} S3: {str(e)}")


def _s3_delete_bucket(
    bucket: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> None:
    try:
        if not client:
            client = get_s3_client(source)
        resp = client.list_objects_v2(Bucket=bucket)
        objects = resp.get("Contents", [])
        if len(objects) > 0:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )
        client.delete_bucket(Bucket=bucket)
    except Exception as e:
        raise Exception(
            f"ERROR: Error deleting bucket {bucket} on {source} S3: {str(e)}"
        )


def _s3_get_object(
    bucket: str,
    path: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> bytes:
    try:
        if not client:
            client = get_s3_client(source)
        return client.get_object(Bucket=bucket, Key=path)["Body"].read()
    except Exception as e:
        raise Exception(
            f"ERROR: Error getting object {bucket}/{path} from S3 on {source}: {str(e)}"
        )


def _s3_put_object(
    bucket: str,
    path: str,
    body: bytes,
    file_type: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> Optional[dict]:
    try:
        started_at = time.monotonic()
        if not client:
            client = get_s3_client(source)
        client.put_object(
            Bucket=bucket,
            Key=path,
            Body=body,
            ContentType=file_type,
        )
        return {
            "source": source,
            "path": f"{bucket}/{path}",
            "size": _size(len(body)),
            "time_to_upload": _duration(time.monotonic() - started_at),
        }
    except Exception as e:
        print(
            f"ERROR: Error uploading object {bucket}/{path} to S3 on {source}: {str(e)}"
        )
        return None


def _s3_delete_object(
    bucket: str,
    path: str,
    source: S3Source,
    client: Optional[boto3.client] = None,
) -> None:
    try:
        if not client:
            client = get_s3_client(source)
        client.delete_object(Bucket=bucket, Key=path)
    except Exception as e:
        raise Exception(
            f"ERROR: Error deleting object {bucket}/{path} from S3 on {source}: {str(e)}"
        )


def check_s3_operations(source: S3Source) -> bool:
    try:
        client = get_s3_client(source)
        _s3_create_bucket(BUCKET, source, client)
        _s3_put_object(
            BUCKET,
            "hello.txt",
            f"Hi from the {source} S3".encode("utf-8"),
            "text/plain",
            source,
            client,
        )
        _s3_get_object(BUCKET, "hello.txt", source, client)
        _s3_delete_object(BUCKET, "hello.txt", source, client)
        return True
    except Exception as e:
        print(f"ERROR: Error checking S3 operations on {source}: {str(e)}")
        return False
