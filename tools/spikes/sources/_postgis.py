import dotenv
import os

dotenv.load_dotenv()

PG_CONN_INFO = (
    f"dbname={os.getenv('POSTGRES_DB', 'mercury')} "
    f"user={os.getenv('POSTGRES_USER', 'mercury')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'mercury')} "
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '15432')} "
)
