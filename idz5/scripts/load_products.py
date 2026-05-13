import json
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta


MANTICORE_BULK_URL = "http://localhost:9308/bulk"
INDEX_NAME = "products"
TOTAL_PRODUCTS = 100_000
BATCH_SIZE = 1000


CATEGORIES = [
    "headphones", "speakers", "laptops", "phones", "gaming",
    "tablets", "monitors", "keyboards", "mice", "cameras"
]

BRANDS = [
    "Sony", "Samsung", "Apple", "Xiaomi", "Lenovo",
    "Asus", "Logitech", "JBL", "Huawei", "Acer"
]

COLORS = [
    "black", "white", "silver", "blue", "red", "green"
]

PRODUCT_PATTERNS = [
    ("wireless bluetooth headphones", "Wireless bluetooth headphones with noise cancelling and long battery life"),
    ("noise cancelling headphones", "Comfortable headphones with active noise cancelling for travel and office"),
    ("portable speaker", "Portable bluetooth speaker with deep bass and waterproof case"),
    ("gaming laptop", "Powerful gaming laptop with fast processor and high refresh rate display"),
    ("business laptop", "Lightweight laptop for work, study and everyday productivity"),
    ("smart phone", "Modern phone with bright display, good camera and fast charging"),
    ("black phone", "Black smartphone with large storage, dual camera and reliable battery"),
    ("gaming mouse", "Gaming mouse with RGB lighting, precise sensor and programmable buttons"),
    ("mechanical keyboard", "Mechanical keyboard for gaming and typing with durable switches"),
    ("4k monitor", "Large 4K monitor with clear image and thin bezels")
]


def random_created_at():
    days_ago = random.randint(0, 730)
    dt = datetime.now() - timedelta(days=days_ago)
    return int(dt.timestamp())


def make_product(product_id):
    title, description = random.choice(PRODUCT_PATTERNS)
    category = random.choice(CATEGORIES)
    brand = random.choice(BRANDS)
    color = random.choice(COLORS)

    # Чтобы поисковые запросы из задания точно находили данные
    if "headphones" in title:
        category = "headphones"
    elif "speaker" in title:
        category = "speakers"
    elif "laptop" in title:
        category = "laptops"
    elif "phone" in title:
        category = "phones"
    elif "gaming" in title:
        category = "gaming"

    full_title = f"{brand} {color} {title} model {product_id}"
    full_description = (
        f"{description}. Brand: {brand}. Color: {color}. "
        f"This product is suitable for home, office, gaming and travel. "
        f"It has many customer reviews and stable quality."
    )

    return {
        "id": product_id,
        "title": full_title,
        "description": full_description,
        "category": category,
        "brand": brand,
        "price": round(random.uniform(1000, 150000), 2),
        "rating": round(random.uniform(3.0, 5.0), 1),
        "reviews_count": random.randint(0, 10000),
        "in_stock": random.choice([True, False]),
        "tags": {
            "color": color,
            "source": "python_generator",
            "condition": "new"
        },
        "created_at": random_created_at()
    }


def send_bulk(products):
    lines = []

    for product in products:
        operation = {
            "insert": {
                "index": INDEX_NAME,
                "id": product["id"],
                "doc": {
                    "title": product["title"],
                    "description": product["description"],
                    "category": product["category"],
                    "brand": product["brand"],
                    "price": product["price"],
                    "rating": product["rating"],
                    "reviews_count": product["reviews_count"],
                    "in_stock": product["in_stock"],
                    "tags": product["tags"],
                    "created_at": product["created_at"]
                }
            }
        }

        lines.append(json.dumps(operation, ensure_ascii=False))

    body = ("\n".join(lines) + "\n").encode("utf-8")

    request = urllib.request.Request(
        MANTICORE_BULK_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-ndjson"}
    )

    try:
        with urllib.request.urlopen(request) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        print(error.read().decode("utf-8"))
        raise


def main():
    start_time = time.time()
    loaded = 0

    print(f"Start loading {TOTAL_PRODUCTS} products into ManticoreSearch")

    for batch_start in range(1, TOTAL_PRODUCTS + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, TOTAL_PRODUCTS + 1)
        products = [make_product(product_id) for product_id in range(batch_start, batch_end)]

        send_bulk(products)

        loaded += len(products)
        print(f"Loaded {loaded}/{TOTAL_PRODUCTS}")

    elapsed = time.time() - start_time
    print(f"Finished loading {loaded} products")
    print(f"Elapsed time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()