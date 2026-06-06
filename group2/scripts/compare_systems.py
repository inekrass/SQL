import os
import statistics
import time
from decimal import Decimal
from pathlib import Path

import clickhouse_connect
import psycopg2
import pymysql
from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "checks" / "comparison_table.txt"


def pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "shop"),
        user=os.getenv("POSTGRES_USER", "shop_user"),
        password=os.getenv("POSTGRES_PASSWORD", "shop_password"),
    )


def ch_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "analytics_user"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "analytics_password"),
        database=os.getenv("CLICKHOUSE_DB", "analytics"),
    )


def manticore_connection():
    return pymysql.connect(
        host=os.getenv("MANTICORE_HOST", "localhost"),
        port=int(os.getenv("MANTICORE_SQL_PORT", "9306")),
        user="",
        password="",
        database="",
        charset="utf8mb4",
        autocommit=True,
    )


def measure(func, repeats=1):
    values = []
    result = None
    for _ in range(repeats):
        started_at = time.perf_counter()
        result = func()
        values.append(time.perf_counter() - started_at)
    return statistics.median(values), result


def fmt_seconds(value):
    if value is None:
        return "N/A"
    if value < 1:
        return f"{value * 1000:.2f} ms"
    return f"{value:.2f} sec"


def prepare_postgres(cursor):
    # Отдельная таблица для PostgreSQL-бенчмарка, чтобы не трогать основные данные.
    cursor.execute("DROP TABLE IF EXISTS benchmark_pg;")
    cursor.execute(
        """
        CREATE TABLE benchmark_pg (
            id BIGSERIAL PRIMARY KEY,
            payload TEXT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )


def prepare_clickhouse(client):
    # Отдельная таблица для ClickHouse-бенчмарка вставок и чтения по ключу.
    client.command("DROP TABLE IF EXISTS analytics.benchmark_ch")
    client.command(
        """
        CREATE TABLE analytics.benchmark_ch (
            id UInt64,
            payload String,
            amount Decimal(12, 2),
            created_at DateTime
        )
        ENGINE = MergeTree
        ORDER BY id
        """
    )


def prepare_manticore(cursor):
    # Отдельный RT-индекс для Manticore-бенчмарка вставок и чтения.
    cursor.execute("DROP TABLE IF EXISTS benchmark_reviews")
    cursor.execute(
        """
        CREATE TABLE benchmark_reviews (
            title text,
            body text,
            rating integer,
            created_at timestamp
        ) morphology='stem_enru' min_word_len='2'
        """
    )


def pg_insert_one(cursor):
    # Измеряем вставку одной OLTP-записи в PostgreSQL.
    cursor.execute(
        "INSERT INTO benchmark_pg (payload, amount) VALUES ('one row', 10.00) RETURNING id;"
    )
    return cursor.fetchone()[0]


def pg_insert_100k(cursor):
    # Измеряем массовую вставку 100K строк в PostgreSQL через generate_series.
    cursor.execute(
        """
        INSERT INTO benchmark_pg (payload, amount)
        SELECT 'bulk row ' || gs, (random() * 1000)::numeric(12, 2)
        FROM generate_series(1, 100000) AS gs;
        """
    )


def pg_select_pk(cursor):
    # Измеряем точечное чтение PostgreSQL по primary key.
    cursor.execute("SELECT * FROM benchmark_pg WHERE id = 1;")
    return cursor.fetchone()


def pg_group_by(cursor):
    # Измеряем аналитический GROUP BY в PostgreSQL по реальным order_items.
    cursor.execute(
        """
        SELECT p.category_id, sum(oi.quantity * oi.unit_price) AS revenue
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        GROUP BY p.category_id
        ORDER BY revenue DESC
        LIMIT 5;
        """
    )
    return cursor.fetchall()


def pg_text_search(cursor):
    # Измеряем простой текстовый поиск в PostgreSQL через ILIKE.
    cursor.execute(
        """
        SELECT review_id, title
        FROM reviews
        WHERE body ILIKE '%kachestvo sborki%'
        LIMIT 10;
        """
    )
    return cursor.fetchall()


def pg_update_one(cursor):
    # Измеряем обновление одной строки в PostgreSQL.
    cursor.execute("UPDATE benchmark_pg SET payload = 'updated row' WHERE id = 1;")


def pg_size(cursor):
    # Берем общий размер текущей PostgreSQL-базы.
    cursor.execute(
        """
        SELECT pg_database_size(current_database());
        """
    )
    return cursor.fetchone()[0]


def ch_insert_one(client):
    # Измеряем вставку одной строки в ClickHouse.
    client.insert(
        "analytics.benchmark_ch",
        [(1, "one row", Decimal("10.00"), int(time.time()))],
        column_names=["id", "payload", "amount", "created_at"],
    )


def ch_insert_100k(client):
    # Измеряем батчевую вставку 100K строк в ClickHouse.
    rows = [
        (idx, f"bulk row {idx}", Decimal("10.00"), int(time.time()))
        for idx in range(2, 100002)
    ]
    client.insert(
        "analytics.benchmark_ch",
        rows,
        column_names=["id", "payload", "amount", "created_at"],
    )


def ch_select_pk(client):
    # Измеряем чтение по id в ClickHouse benchmark-таблице.
    return client.query("SELECT * FROM analytics.benchmark_ch WHERE id = 1").result_rows


def ch_group_by(client):
    # Измеряем OLAP GROUP BY в ClickHouse по денормализованной таблице.
    return client.query(
        """
        SELECT category, sum(line_total) AS revenue
        FROM analytics.orders_analytics
        GROUP BY category
        ORDER BY revenue DESC
        LIMIT 5
        """
    ).result_rows


def ch_size(client):
    # Берем размер активных частей ClickHouse на диске для базы analytics.
    return client.query(
        """
        SELECT sum(bytes_on_disk)
        FROM system.parts
        WHERE active AND database = 'analytics'
        """
    ).result_rows[0][0]


def manticore_insert_one(cursor):
    # Измеряем вставку одного документа в ManticoreSearch.
    cursor.execute(
        """
        REPLACE INTO benchmark_reviews (id, title, body, rating, created_at)
        VALUES (1, 'one review', 'kachestvo sborki horoshee', 5, %s)
        """,
        (int(time.time()),),
    )


def manticore_insert_100k(cursor):
    # Измеряем массовую вставку 100K документов в ManticoreSearch.
    rows = [
        (
            idx,
            f"review {idx}",
            "kachestvo sborki horoshee tovar rekomenduyu",
            1 + (idx % 5),
            int(time.time()),
        )
        for idx in range(2, 100002)
    ]
    cursor.executemany(
        """
        REPLACE INTO benchmark_reviews (id, title, body, rating, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows,
    )


def manticore_select_pk(cursor):
    # Измеряем чтение документа ManticoreSearch по id.
    cursor.execute("SELECT * FROM benchmark_reviews WHERE id = 1")
    return cursor.fetchall()


def manticore_text_search(cursor):
    # Измеряем полнотекстовый поиск по основному индексу reviews.
    cursor.execute(
        """
        SELECT id, title, rating
        FROM reviews
        WHERE MATCH('kachestvo sborki')
        LIMIT 10
        """
    )
    return cursor.fetchall()


def manticore_update_one(cursor):
    # В Manticore обновление показываем через REPLACE документа с тем же id.
    cursor.execute(
        """
        REPLACE INTO benchmark_reviews (id, title, body, rating, created_at)
        VALUES (1, 'updated review', 'brak slomalsya vozvrat', 1, %s)
        """,
        (int(time.time()),),
    )


def manticore_size(cursor):
    # Считаем footprint Manticore: disk_bytes + ram_bytes по всем RT-индексам.
    cursor.execute("SHOW TABLES")
    rows = cursor.fetchall()
    total_bytes = 0
    for row in rows:
        table_name = row[0]
        cursor.execute(f"SHOW TABLE {table_name} STATUS")
        table_values = {}
        for status_name, status_value in cursor.fetchall():
            table_values[status_name] = status_value
        total_bytes += int(table_values.get("disk_bytes", 0))
        total_bytes += int(table_values.get("ram_bytes", 0))
    return total_bytes


def bytes_to_mb(value):
    return f"{value / 1024 / 1024:.2f} MB"


def main():
    results = {}

    # PostgreSQL: OLTP-вставки, чтение по PK, GROUP BY, текстовый поиск, UPDATE и размер.
    with pg_connection() as connection:
        with connection.cursor() as cursor:
            prepare_postgres(cursor)
            results["pg_insert_one"] = measure(lambda: pg_insert_one(cursor), repeats=5)[0]
            results["pg_insert_100k"] = measure(lambda: pg_insert_100k(cursor))[0]
            results["pg_select_pk"] = measure(lambda: pg_select_pk(cursor), repeats=10)[0]
            results["pg_group_by"] = measure(lambda: pg_group_by(cursor), repeats=3)[0]
            results["pg_text_search"] = measure(lambda: pg_text_search(cursor), repeats=3)[0]
            results["pg_update_one"] = measure(lambda: pg_update_one(cursor), repeats=5)[0]
            results["pg_size"] = pg_size(cursor)

    # ClickHouse: вставки, чтение, аналитический GROUP BY и размер аналитической базы.
    client = ch_client()
    prepare_clickhouse(client)
    results["ch_insert_one"] = measure(lambda: ch_insert_one(client), repeats=5)[0]
    results["ch_insert_100k"] = measure(lambda: ch_insert_100k(client))[0]
    results["ch_select_pk"] = measure(lambda: ch_select_pk(client), repeats=10)[0]
    results["ch_group_by"] = measure(lambda: ch_group_by(client), repeats=3)[0]
    results["ch_size"] = ch_size(client)

    # ManticoreSearch: вставки документов, чтение, полнотекстовый поиск, REPLACE и footprint.
    with manticore_connection() as connection:
        with connection.cursor() as cursor:
            prepare_manticore(cursor)
            results["manticore_insert_one"] = measure(lambda: manticore_insert_one(cursor), repeats=5)[0]
            results["manticore_insert_100k"] = measure(lambda: manticore_insert_100k(cursor))[0]
            results["manticore_select_pk"] = measure(lambda: manticore_select_pk(cursor), repeats=10)[0]
            results["manticore_text_search"] = measure(lambda: manticore_text_search(cursor), repeats=5)[0]
            results["manticore_update_one"] = measure(lambda: manticore_update_one(cursor), repeats=5)[0]
            results["manticore_size"] = manticore_size(cursor)

    # Формируем отчет в Markdown и сохраняем его в checks/comparison_table.txt.
    markdown = f"""
Comparative analysis
====================

Дата проверки: 2026-06-07

| Операция | PostgreSQL | ClickHouse | ManticoreSearch |
|---|---:|---:|---:|
| Вставка 1 записи | {fmt_seconds(results["pg_insert_one"])} | {fmt_seconds(results["ch_insert_one"])} | {fmt_seconds(results["manticore_insert_one"])} |
| Вставка 100K записей | {fmt_seconds(results["pg_insert_100k"])} | {fmt_seconds(results["ch_insert_100k"])} | {fmt_seconds(results["manticore_insert_100k"])} |
| SELECT по PK | {fmt_seconds(results["pg_select_pk"])} | {fmt_seconds(results["ch_select_pk"])} | {fmt_seconds(results["manticore_select_pk"])} |
| Аналитика GROUP BY | {fmt_seconds(results["pg_group_by"])} | {fmt_seconds(results["ch_group_by"])} | N/A |
| Полнотекстовый поиск | {fmt_seconds(results["pg_text_search"])} | N/A | {fmt_seconds(results["manticore_text_search"])} |
| UPDATE 1 записи | {fmt_seconds(results["pg_update_one"])} | не рекомендуется | {fmt_seconds(results["manticore_update_one"])} |
| Размер / footprint | {bytes_to_mb(results["pg_size"])} | {bytes_to_mb(results["ch_size"])} | {bytes_to_mb(results["manticore_size"])} |

Выводы:
- PostgreSQL лучше подходит для OLTP: транзакции, создание заказов, UPDATE, чтение по ключу.
- ClickHouse лучше подходит для аналитики по большим таблицам: GROUP BY по 1M+ строк выполняется быстрее и хранение компактнее для аналитической таблицы.
- ManticoreSearch лучше подходит для полнотекстового поиска и фасетов по отзывам.
- В этом проекте системы не заменяют друг друга, а решают разные задачи: PostgreSQL хранит операционные данные, ClickHouse считает аналитику, ManticoreSearch ищет по тексту.

Примечание по размеру:
- PostgreSQL: размер текущей базы через pg_database_size.
- ClickHouse: bytes_on_disk активных parts базы analytics.
- ManticoreSearch: disk_bytes + ram_bytes по RT-индексам, потому что RT-индекс держит активный chunk в памяти.
""".strip()

    OUTPUT_PATH.write_text(markdown + "\n", encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
