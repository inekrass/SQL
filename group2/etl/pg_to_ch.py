import os
from decimal import Decimal
from datetime import datetime, timezone
import json
from pathlib import Path

import clickhouse_connect
import psycopg2
from dotenv import load_dotenv


load_dotenv()

BATCH_SIZE = int(os.getenv("ETL_BATCH_SIZE", "50000"))
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STATE_PATH = PROJECT_ROOT / "monitoring" / "pipeline_state.json"

PG_QUERY = """
SELECT
    o.created_at::date AS order_date,
    o.order_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.region,
    p.name AS product_name,
    cat.name AS category,
    oi.quantity,
    oi.unit_price AS price,
    oi.quantity * oi.unit_price AS line_total,
    o.status AS order_status
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN categories cat ON cat.category_id = p.category_id
ORDER BY o.order_id, oi.order_item_id;
"""


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "shop"),
        user=os.getenv("POSTGRES_USER", "shop_user"),
        password=os.getenv("POSTGRES_PASSWORD", "shop_password"),
    )


def get_ch_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "analytics_user"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "analytics_password"),
        database=os.getenv("CLICKHOUSE_DB", "analytics"),
    )


def normalize_row(row):
    return (
        row[0],
        int(row[1]),
        row[2],
        row[3],
        row[4],
        row[5],
        int(row[6]),
        Decimal(row[7]),
        Decimal(row[8]),
        row[9],
    )


def main():
    total_rows = run_etl()
    print(f"ETL finished, total rows loaded: {total_rows}")


def run_etl():
    client = get_ch_client()
    client.command("TRUNCATE TABLE analytics.orders_analytics")

    columns = [
        "order_date",
        "order_id",
        "customer_name",
        "region",
        "product_name",
        "category",
        "quantity",
        "price",
        "line_total",
        "order_status",
    ]
    total_rows = 0

    with get_pg_connection() as pg_connection:
        with pg_connection.cursor(name="orders_analytics_cursor") as cursor:
            cursor.itersize = BATCH_SIZE
            cursor.execute(PG_QUERY)

            while True:
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break

                batch = [normalize_row(row) for row in rows]
                client.insert("analytics.orders_analytics", batch, column_names=columns)
                total_rows += len(batch)
                print(f"loaded rows: {total_rows}")

    update_pipeline_state("clickhouse", total_rows)
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
