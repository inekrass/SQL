import os
from decimal import Decimal
import psycopg2
import clickhouse_connect


PG_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5433")),
    "dbname": os.getenv("PG_DB", "idz1"),
    "user": os.getenv("PG_USER", "inekrass"),
    "password": os.getenv("PG_PASSWORD", "inekrass"),
}

CH_CONFIG = {
    "host": os.getenv("CH_HOST", "localhost"),
    "port": int(os.getenv("CH_PORT", "8123")),
    "username": os.getenv("CH_USER", "default"),
    "password": os.getenv("CH_PASSWORD", ""),
    "database": os.getenv("CH_DB", "idz2"),
}


PG_QUERY = """
SELECT
    o.order_date AS order_date,
    o.order_date::timestamp AS order_datetime,
    o.order_id,
    c.customer_id,
    c.customer_name,
    c.customer_email,
    COALESCE(a.address, 'unknown') AS region,
    p.product_id,
    p.product_name,
    COALESCE(cat.category_name, 'unknown') AS category,
    oi.quantity,
    oi.price_at_order AS price,
    (oi.quantity * oi.price_at_order) AS line_total,
    o.status AS order_status
FROM orders_3nf o
JOIN customers_3nf c
    ON c.customer_id = o.customer_id
LEFT JOIN addresses a
    ON a.address_id = o.address_id
JOIN order_items_3nf oi
    ON oi.order_id = o.order_id
JOIN products_3nf p
    ON p.product_id = oi.product_id
LEFT JOIN categories cat
    ON cat.category_id = p.category_id
ORDER BY o.order_id, p.product_id;
"""


def fetch_pg_rows():
    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(PG_QUERY)
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()


def normalize_rows(rows):
    result = []
    for row in rows:
        result.append([
            row[0],                    # order_date
            row[1],                    # order_datetime
            int(row[2]),               # order_id
            int(row[3]),               # customer_id
            row[4],                    # customer_name
            row[5],                    # customer_email
            row[6],                    # region
            int(row[7]),               # product_id
            row[8],                    # product_name
            row[9],                    # category
            int(row[10]),              # quantity
            Decimal(row[11]),          # price
            Decimal(row[12]),          # line_total
            row[13],                   # order_status
        ])
    return result


def insert_into_clickhouse(rows):
    client = clickhouse_connect.get_client(**CH_CONFIG)

    column_names = [
        "order_date",
        "order_datetime",
        "order_id",
        "customer_id",
        "customer_name",
        "customer_email",
        "region",
        "product_id",
        "product_name",
        "category",
        "quantity",
        "price",
        "line_total",
        "order_status",
    ]

    client.command("TRUNCATE TABLE idz2.orders_flat")
    client.command("TRUNCATE TABLE idz2.orders_ttl")

    client.insert("idz2.orders_flat", rows, column_names=column_names)
    client.insert("idz2.orders_ttl", rows, column_names=column_names)

    print(f"Inserted {len(rows)} rows into idz2.orders_flat")
    print(f"Inserted {len(rows)} rows into idz2.orders_ttl")


def main():
    print("Reading data from PostgreSQL...")
    pg_rows = fetch_pg_rows()
    print(f"Fetched {len(pg_rows)} rows from PostgreSQL")

    ch_rows = normalize_rows(pg_rows)

    print("Loading data into ClickHouse...")
    insert_into_clickhouse(ch_rows)

    print("Done.")


if __name__ == "__main__":
    main()