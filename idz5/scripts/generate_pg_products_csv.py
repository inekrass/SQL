import csv
import json
import random
from datetime import datetime, timedelta


OUTPUT_FILE = "/tmp/pg_products.csv"
TOTAL_PRODUCTS = 100_000

random.seed(42)

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
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def make_product(product_id):
    title, description = random.choice(PRODUCT_PATTERNS)
    category = random.choice(CATEGORIES)
    brand = random.choice(BRANDS)
    color = random.choice(COLORS)

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

    tags = {
        "color": color,
        "source": "python_generator",
        "condition": "new"
    }

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
        "tags": json.dumps(tags),
        "created_at": random_created_at()
    }


def main():
    fieldnames = [
        "id",
        "title",
        "description",
        "category",
        "brand",
        "price",
        "rating",
        "reviews_count",
        "in_stock",
        "tags",
        "created_at"
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for product_id in range(1, TOTAL_PRODUCTS + 1):
            writer.writerow(make_product(product_id))

    print(f"Generated {TOTAL_PRODUCTS} products into {OUTPUT_FILE}")


if __name__ == "__main__":
    main()