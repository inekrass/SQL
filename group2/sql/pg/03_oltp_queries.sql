-- 1. Создание заказа в транзакции.
BEGIN;

INSERT INTO orders (customer_id, status)
VALUES (1, 'new')
RETURNING order_id;

-- Для проверки можно подставить order_id, который вернул предыдущий INSERT.
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
VALUES
    (currval('orders_order_id_seq'), 1, 2, (SELECT price FROM products WHERE product_id = 1)),
    (currval('orders_order_id_seq'), 2, 1, (SELECT price FROM products WHERE product_id = 2));

COMMIT;

-- 2. Обновление статуса заказа.
UPDATE orders
SET status = 'paid',
    updated_at = now()
WHERE order_id = 1;

-- 3. Чтение заказа с JOIN-ами.
SELECT
    o.order_id,
    o.status,
    o.created_at,
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.region,
    p.product_id,
    p.name AS product_name,
    cat.name AS category_name,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_total
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN categories cat ON cat.category_id = p.category_id
WHERE o.order_id = 1
ORDER BY oi.order_item_id;

-- 4. Проверка количества данных.
SELECT 'customers' AS table_name, count(*) AS rows_count FROM customers
UNION ALL
SELECT 'products', count(*) FROM products
UNION ALL
SELECT 'orders', count(*) FROM orders
UNION ALL
SELECT 'order_items', count(*) FROM order_items
UNION ALL
SELECT 'reviews', count(*) FROM reviews;
