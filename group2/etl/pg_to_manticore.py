import os
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path

import psycopg2
import pymysql
from dotenv import load_dotenv


load_dotenv()

BATCH_SIZE = int(os.getenv("MANTICORE_BATCH_SIZE", "10000"))
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STATE_PATH = PROJECT_ROOT / "monitoring" / "pipeline_state.json"

PG_QUERY = """
SELECT
    review_id,
    title,
    body,
    product_id,
    customer_id,
    rating,
    created_at
FROM reviews
ORDER BY review_id;
"""


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "shop"),
        user=os.getenv("POSTGRES_USER", "shop_user"),
        password=os.getenv("POSTGRES_PASSWORD", "shop_password"),
    )


def get_manticore_connection():
    return pymysql.connect(
        host=os.getenv("MANTICORE_HOST", "localhost"),
        port=int(os.getenv("MANTICORE_SQL_PORT", "9306")),
        user="",
        password="",
        database="",
        charset="utf8mb4",
        autocommit=True,
    )


def created_at_to_timestamp(value):
    if isinstance(value, datetime):
        return int(value.timestamp())
    return int(datetime.fromisoformat(str(value)).timestamp())


def insert_batch(cursor, rows):
    values = [
        (
            int(row[0]),
            row[1],
            row[2],
            int(row[3]),
            int(row[4]),
            int(row[5]),
            created_at_to_timestamp(row[6]),
        )
        for row in rows
    ]
    cursor.executemany(
        """
        REPLACE INTO reviews
            (id, title, body, product_id, customer_id, rating, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s)
        """,
        values,
    )


def main():
    total_rows = run_etl()
    print(f"Manticore ETL finished, total reviews loaded: {total_rows}")


def run_etl():
    total_rows = 0

    with get_pg_connection() as pg_connection:
        with pg_connection.cursor(name="reviews_cursor") as pg_cursor:
            pg_cursor.itersize = BATCH_SIZE
            pg_cursor.execute(PG_QUERY)

            with get_manticore_connection() as manticore_connection:
                with manticore_connection.cursor() as manticore_cursor:
                    manticore_cursor.execute("TRUNCATE TABLE reviews")

                    while True:
                        rows = pg_cursor.fetchmany(BATCH_SIZE)
                        if not rows:
                            break

                        insert_batch(manticore_cursor, rows)
                        total_rows += len(rows)
                        print(f"loaded reviews: {total_rows}")

    update_pipeline_state("manticore", total_rows)
    return total_rows


def update_pipeline_state(target, rows_count):
    PIPELINE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PIPELINE_STATE_PATH.exists():
        with PIPELINE_STATE_PATH.open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    else:
        state = {}

    state[target] = {
        "last_sync_at": datetime.now(timezone.utc).isoformat(),
        "processed_records": rows_count,
    }

    with PIPELINE_STATE_PATH.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)


if __name__ == "__main__":
    main()
