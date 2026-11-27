import dagster as dg
import pandas as pd
import traceback

from dagster_aws.s3 import S3PickleIOManager, S3Resource

from _aws import BUCKET, S3Source, get_s3_access


def _s3_resource(source: S3Source) -> S3Resource:
    access = get_s3_access(source)
    return S3Resource(
        endpoint_url=access["url"],
        aws_access_key_id=access["access_key"],
        aws_secret_access_key=access["secret_key"],
        use_ssl=access["url"].startswith("https"),
        region_name="us-east-1",
    )


@dg.asset
def spike_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "municipality_id": [3550308, 3550308, 3550308, 3304557],
            "uf": ["SP", "SP", "SP", "RJ"],
            "accidents": [1, 2, 1, 1],
            "precipitation_mm": [0.0, 1.4, 1.4, None],
        }
    )


@dg.asset
def spike_frame_roundtrip(spike_frame: pd.DataFrame) -> int:
    if len(spike_frame) != 4 or not all(spike_frame["accidents"].isin([1, 2])):
        raise Exception("S3 IO manager returned different data")
    return len(spike_frame)


def check_dagster_s3_io(source: S3Source) -> bool:
    try:
        result = dg.materialize(
            [spike_frame, spike_frame_roundtrip],
            resources={
                "io_manager": S3PickleIOManager(
                    s3_resource=_s3_resource(source),
                    s3_bucket=BUCKET,
                    s3_prefix="spike/dagster-io",
                )
            },
        )
        return result.success
    except Exception as e:
        print(f"ERROR: Error checking Dagster S3 IO on {source}: {str(e)}")
        traceback.print_exc()
        return False
