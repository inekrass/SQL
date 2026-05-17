DROP TABLE IF EXISTS pg_products;

CREATE TABLE pg_products (
    id BIGINT PRIMARY KEY,
    title TEXT,
    description TEXT,
    category TEXT,
    brand TEXT,
    price NUMERIC,
    rating NUMERIC,
    reviews_count INTEGER,
    in_stock BOOLEAN,
    tags JSONB,
    created_at TIMESTAMP,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED
);

COPY pg_products (
    id,
    title,
    description,
    category,
    brand,
    price,
    rating,
    reviews_count,
    in_stock,
    tags,
    created_at
)
FROM '/tmp/pg_products.csv'
WITH (FORMAT csv, HEADER true);

CREATE INDEX idx_pg_products_tsv
ON pg_products
USING GIN(tsv);

ANALYZE pg_products;

EXPLAIN ANALYZE
SELECT title, ts_rank(tsv, q) AS rank
FROM pg_products, to_tsquery('english', 'wireless & bluetooth & headphones') q
WHERE tsv @@ q
ORDER BY rank DESC
LIMIT 10;