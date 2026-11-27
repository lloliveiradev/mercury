import clickhouse_connect as chn
import dotenv
import os

dotenv.load_dotenv()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", 18123))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "mercury")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "mercury")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "mercury")


class ClickHouse:
    def __init__(self):
        self.ch = chn.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
        )

    def query(self, query: str) -> list[dict]:
        return self.ch.query(query).result_set
