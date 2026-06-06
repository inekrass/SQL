from decimal import Decimal
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from etl.pg_to_ch import get_ch_client, run_etl as run_ch_etl
from etl.pg_to_manticore import get_manticore_connection, run_etl as run_manticore_etl
from etl.pg_to_ch import get_pg_connection


def create_order():
    with get_pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT customer_id
                FROM customers
                ORDER BY customer_id
                LIMIT 1;
                """
            )
            customer_id = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT product_id, price
                FROM products
                ORDER BY product_id
                LIMIT 2;
                """
            )
            products = cursor.fetchall()

            cursor.execute(
                """
                INSERT INTO orders (customer_id, status)
                VALUES (%s, 'new')
                RETURNING order_id;
                """,
                (customer_id,),
            )
            order_id = cursor.fetchone()[0]

            for product_id, price in products:
                cursor.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (order_id, product_id, 1, price),
                )

    return order_id


def run_clickhouse_analytics():
    client = get_ch_client()
    return client.query(
        """
        SELECT
            category,
            sum(line_total) AS revenue
        FROM analytics.orders_analytics
        GROUP BY category
        ORDER BY revenue DESC
        LIMIT 5
        """
    ).result_rows


def add_review():
    with get_pg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reviews (product_id, customer_id, rating, title, body)
                VALUES (
                    42,
                    1,
                    5,
                    'Demo review',
                    'kachestvo sborki otlichnoe tovar rekomenduyu'
                )
                RETURNING review_id;
                """
            )
            review_id = cursor.fetchone()[0]

    return review_id


def search_review():
    with get_manticore_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, product_id, customer_id, rating, title
                FROM reviews
                WHERE MATCH('kachestvo sborki')
                LIMIT 5
                """
            )
            return cursor.fetchall()


def format_money(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def main():
    print("1. Create order in PostgreSQL")
    order_id = create_order()
    print(f"created order_id: {order_id}")

    print("\n2. Run ETL PostgreSQL -> ClickHouse")
    ch_rows = run_ch_etl()
    print(f"ClickHouse rows loaded: {ch_rows}")

    print("\n3. Run analytics query in ClickHouse: top-5 categories by revenue")
    for category, revenue in run_clickhouse_analytics():
        print(f"{category}: {format_money(revenue)}")

    print("\n4. Add review in PostgreSQL")
    review_id = add_review()
    print(f"created review_id: {review_id}")

    print("\n5. Sync reviews PostgreSQL -> ManticoreSearch")
    manticore_rows = run_manticore_etl()
    print(f"Manticore reviews loaded: {manticore_rows}")

    print("\n6. Full-text search in ManticoreSearch")
    for row in search_review():
        print(row)


if __name__ == "__main__":
    main()
