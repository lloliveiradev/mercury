import boto3
import dotenv
import os

from dagster_aws.s3 import S3Resource

dotenv.load_dotenv()

s3 = boto3.client("s3")
BUCKET = "mercury-data"


def get_emulator_access() -> dict:
    access_key = None
    secret_key = None
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


def _s3() -> S3Resource:
    access = get_emulator_access()
    return S3Resource(
        endpoint_url=access["url"],
        aws_access_key_id=access["access_key"],
        aws_secret_access_key=access["secret_key"],
        use_ssl=access["url"].startswith("https"),
    )
