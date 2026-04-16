-- Часть 4.2 Денормализация через избыточное поле

-- 1. Добавляем избыточное поле с названием товара

ALTER TABLE order_items_3nf
ADD COLUMN product_name TEXT;

-- 2. Заполняем его значениями из таблицы products

UPDATE order_items_3nf oi
SET product_name = p.product_name
FROM products_3nf p
WHERE oi.product_id = p.product_id;

-- 3. Запрос без JOIN (используем денормализованное поле)

EXPLAIN ANALYZE
SELECT
    order_id,
    product_name,
    quantity,
    price_at_order
FROM order_items_3nf
WHERE product_name ILIKE '%Мышь%';

-- 4. Такой же запрос, но через JOIN

EXPLAIN ANALYZE
SELECT
    oi.order_id,
    p.product_name,
    oi.quantity,
    oi.price_at_order
FROM order_items_3nf oi
JOIN products_3nf p
ON p.product_id = oi.product_id
WHERE p.product_name ILIKE '%Мышь%';