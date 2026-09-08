import os
from contextlib import contextmanager
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URI = os.getenv("DATABASE_URI", "postgresql://user:password@localhost:5432/supplychain?sslmode=disable")

# Use a connection pool for better performance across multiple API requests
pool = ConnectionPool(
    conninfo=DATABASE_URI,
    max_size=20,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

def setup_db():
    with pool.connection() as conn:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()

@contextmanager
def get_checkpointer():
    with pool.connection() as conn:
        yield PostgresSaver(conn)
