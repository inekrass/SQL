import csv
import os
import random
from datetime import datetime, timedelta, timezone
from io import StringIO

import psycopg2
from dotenv import load_dotenv


load_dotenv()


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


CUSTOMERS_COUNT = env_int("SEED_CUSTOMERS", 50_000)
PRODUCTS_COUNT = env_int("SEED_PRODUCTS", 5_000)
ORDERS_COUNT = env_int("SEED_ORDERS", 500_000)
REVIEWS_COUNT = env_int("SEED_REVIEWS", 200_000)
BATCH_SIZE = env_int("SEED_BATCH_SIZE", 20_000)

RANDOM_SEED = env_int("SEED_RANDOM", 42)
random.seed(RANDOM_SEED)

FIRST_NAMES = [
    "Ivan", "Petr", "Anna", "Maria", "Oleg", "Daria", "Nikolay", "Sofia",
    "Mikhail", "Elena", "Sergey", "Alina", "Alexey", "Polina", "Kirill",
]
LAST_NAMES = [
    "Ivanov", "Petrov", "Sidorov", "Smirnov", "Volkov", "Fedorov",
    "Kuznetsov", "Popov", "Orlov", "Morozov", "Lebedev", "Novikov",
]
REGIONS = ["Moscow", "SPb", "Ural", "Siberia", "South", "Volga", "Far East"]
CITIES = ["Moscow", "Saint Petersburg", "Kazan", "Ekaterinburg", "Novosibirsk", "Sochi"]
CATEGORIES = [
    "Smartphones", "Laptops", "TV", "Audio", "Home appliances", "Furniture",
    "Clothes", "Shoes", "Sport", "Books", "Toys", "Beauty", "Auto", "Garden",
    "Tools", "Food", "Pet supplies", "Office", "Gaming", "Accessories",
]
STATUSES = ["new", "paid", "shipped", "delivered", "cancelled"]
REVIEW_TITLES = [
    "Good product", "Great quality", "Fast delivery", "Not bad", "Expected better",
    "Broken item", "I recommend", "Good price", "Poor packaging", "Works fine",
]
REVIEW_BODIES = [
    "otlichnyy tovar rekomenduyu, kachestvo sborki horoshee",
    "dostavka bystraya, opisanie sootvetstvuet tovaru",
    "brak slomalsya vozvrat, nuzhna zamena",
    "normalnyy tovar za svoi dengi, pokupkoy dovolen",
    "kachestvo sborki srednee, no rabotaet stabilno",
    "upakovka slabaya, no sam tovar bez povrezhdeniy",
]


def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "shop"),
        user=os.getenv("POSTGRES_USER", "shop_user"),
        password=os.getenv("POSTGRES_PASSWORD", "shop_password"),
    )


def copy_rows(cursor, table: str, columns: list[str], rows):
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    cursor.copy_from(buffer, table, columns=columns, sep="\t", null="\\N")


def chunks(total: int, size: int):
    start = 1
    while start <= total:
        end = min(start + size - 1, total)
        yield start, end
        start = end + 1


def reset_tables(cursor):
    cursor.execute(
        """
        TRUNCATE reviews, order_items, orders, products, categories, customers
        RESTART IDENTITY CASCADE;
        """
    )


def seed_categories(cursor):
    rows = [(idx, name, "\\N") for idx, name in enumerate(CATEGORIES, start=1)]
    copy_rows(cursor, "categories", ["category_id", "name", "parent_category_id"], rows)


def seed_customers(cursor):
    for start, end in chunks(CUSTOMERS_COUNT, BATCH_SIZE):
        rows = []
        for customer_id in range(start, end + 1):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            rows.append(
                (
                    customer_id,
                    first_name,
                    last_name,
                    f"user{customer_id}@example.com",
                    f"+7999{customer_id:07d}",
                    random.choice(REGIONS),
                    random.choice(CITIES),
                    datetime.now(timezone.utc).isoformat(),
                )
            )
        copy_rows(
            cursor,
            "customers",
            ["customer_id", "first_name", "last_name", "email", "phone", "region", "city", "created_at"],
            rows,
        )
        print(f"customers: {end}/{CUSTOMERS_COUNT}")


def seed_products(cursor):
    for start, end in chunks(PRODUCTS_COUNT, BATCH_SIZE):
        rows = []
        for product_id in range(start, end + 1):
            category_id = ((product_id - 1) % len(CATEGORIES)) + 1
            price = round(random.uniform(100, 120_000), 2)
            rows.append(
                (
                    product_id,
                    category_id,
                    f"SKU-{product_id:06d}",
                    f"Product {product_id}",
                    f"Product {product_id} description",
                    price,
                    True,
                    datetime.now(timezone.utc).isoformat(),
                )
            )
        copy_rows(
            cursor,
            "products",
            ["product_id", "category_id", "sku", "name", "description", "price", "is_active", "created_at"],
            rows,
        )
        print(f"products: {end}/{PRODUCTS_COUNT}")


def seed_orders_and_items(cursor):
    order_item_id = 1
    base_date = datetime.now(timezone.utc) - timedelta(days=365)

    for start, end in chunks(ORDERS_COUNT, BATCH_SIZE):
        order_rows = []
        item_rows = []
        for order_id in range(start, end + 1):
            created_at = base_date + timedelta(minutes=order_id)
            updated_at = created_at + timedelta(hours=random.randint(1, 72))
            status = random.choices(STATUSES, weights=[8, 25, 25, 35, 7], k=1)[0]
            customer_id = random.randint(1, CUSTOMERS_COUNT)

            order_rows.append((order_id, customer_id, status, created_at.isoformat(), updated_at.isoformat()))

            for _ in range(random.randint(1, 4)):
                product_id = random.randint(1, PRODUCTS_COUNT)
                quantity = random.randint(1, 5)
                unit_price = round(random.uniform(100, 120_000), 2)
                item_rows.append((order_item_id, order_id, product_id, quantity, unit_price))
                order_item_id += 1

        copy_rows(cursor, "orders", ["order_id", "customer_id", "status", "created_at", "updated_at"], order_rows)
        copy_rows(
            cursor,
            "order_items",
            ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
            item_rows,
        )
        print(f"orders: {end}/{ORDERS_COUNT}, order_items: {order_item_id - 1}")


def seed_reviews(cursor):
    base_date = datetime.now(timezone.utc) - timedelta(days=180)
    for start, end in chunks(REVIEWS_COUNT, BATCH_SIZE):
        rows = []
        for review_id in range(start, end + 1):
            created_at = base_date + timedelta(minutes=review_id)
            rows.append(
                (
                    review_id,
                    random.randint(1, PRODUCTS_COUNT),
                    random.randint(1, CUSTOMERS_COUNT),
                    random.randint(1, 5),
                    random.choice(REVIEW_TITLES),
                    random.choice(REVIEW_BODIES),
                    created_at.isoformat(),
                )
            )
        copy_rows(
            cursor,
            "reviews",
            ["review_id", "product_id", "customer_id", "rating", "title", "body", "created_at"],
            rows,
        )
        print(f"reviews: {end}/{REVIEWS_COUNT}")


def refresh_sequences(cursor):
    sequence_pairs = [
        ("customers_customer_id_seq", "customers", "customer_id"),
        ("categories_category_id_seq", "categories", "category_id"),
        ("products_product_id_seq", "products", "product_id"),
        ("orders_order_id_seq", "orders", "order_id"),
        ("order_items_order_item_id_seq", "order_items", "order_item_id"),
        ("reviews_review_id_seq", "reviews", "review_id"),
    ]
    for sequence, table, column in sequence_pairs:
        cursor.execute(
            "SELECT setval(%s::regclass, COALESCE((SELECT max(" + column + ") FROM " + table + "), 1));",
            (sequence,),
        )


def print_counts(cursor):
    cursor.execute(
        """
        SELECT 'customers', count(*) FROM customers
        UNION ALL SELECT 'categories', count(*) FROM categories
        UNION ALL SELECT 'products', count(*) FROM products
        UNION ALL SELECT 'orders', count(*) FROM orders
        UNION ALL SELECT 'order_items', count(*) FROM order_items
        UNION ALL SELECT 'reviews', count(*) FROM reviews
        ORDER BY 1;
        """
    )
    for table_name, rows_count in cursor.fetchall():
        print(f"{table_name}: {rows_count}")


def main():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            reset_tables(cursor)
            seed_categories(cursor)
            seed_customers(cursor)
            seed_products(cursor)
            seed_orders_and_items(cursor)
            seed_reviews(cursor)
            refresh_sequences(cursor)
            print_counts(cursor)


if __name__ == "__main__":
    main()
