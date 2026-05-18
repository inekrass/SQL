-- 7.1 UPDATE: продукт до обновления
SELECT id, title, price, rating
FROM products
WHERE id = 1;

-- UPDATE цены и рейтинга продукта
UPDATE products
SET price = 9999.99, rating = 4.9
WHERE id = 1;

-- Продукт после обновления
SELECT id, title, price, rating
FROM products
WHERE id = 1;


-- 7.2 DELETE: продукт до удаления
SELECT id, title
FROM products
WHERE id = 2;

-- Delete product
DELETE FROM products
WHERE id = 2;

-- Продукт после удаления
SELECT id, title
FROM products
WHERE id = 2;


-- 7.3 REPLACE: продукт до замены
SELECT id, title, description, category, brand, price, rating, tags
FROM products
WHERE id = 3;

-- Replace
REPLACE INTO products (
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
VALUES (
    3,
    'Demo replaced black phone',
    'This document was fully replaced with REPLACE operation. Black phone with fast charging and updated description.',
    'phones',
    'DemoBrand',
    55555.55,
    4.8,
    777,
    1,
    '{"color":"black","source":"replace_demo","condition":"new"}',
    1710000000
);

-- Продукт после замены
SELECT id, title, description, category, brand, price, rating, reviews_count, in_stock, tags, created_at
FROM products
WHERE id = 3;