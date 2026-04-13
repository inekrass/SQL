-- 1. Создание заказа
-- Транзакция: создаем заказ и позиции заказа
-- С проверкой товара через SELECT ... FOR UPDATE
BEGIN;

-- Проверяем и блокируем товар
SELECT *
FROM products_3nf
WHERE product_id = 1
FOR UPDATE;

-- Создаем заказ
INSERT INTO orders_3nf (order_id, customer_id, address_id, order_date, status, total_amount)
VALUES (1001, 1, 1, CURRENT_DATE, 'new', 1500);

-- Добавляем позицию заказа
INSERT INTO order_items_3nf (order_id, product_id, quantity, price_at_order)
VALUES (1001, 1, 1, 1500);

COMMIT;

EXPLAIN ANALYZE
SELECT *
FROM products_3nf
WHERE product_id = 1
FOR UPDATE;

EXPLAIN ANALYZE
INSERT INTO orders_3nf (order_id, customer_id, address_id, order_date, status, total_amount)
VALUES (1002, 1, 1, CURRENT_DATE, 'new', 1500);

EXPLAIN ANALYZE
INSERT INTO order_items_3nf (order_id, product_id, quantity, price_at_order)
VALUES (1002, 1, 1, 1500);

-- 2. Обновление статуса заказа

UPDATE orders_3nf
SET status = 'shipped'
WHERE order_id = 1;

EXPLAIN ANALYZE
UPDATE orders_3nf
SET status = 'shipped'
WHERE order_id = 1;

-- 3. Получение заказа
-- JOIN по 4 таблицам:
-- orders_3nf + customers_3nf + order_items_3nf + products_3nf

SELECT
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount,
    c.customer_name,
    c.customer_email,
    p.product_name,
    oi.quantity,
    oi.price_at_order
FROM orders_3nf o
JOIN customers_3nf c
    ON c.customer_id = o.customer_id
JOIN order_items_3nf oi
    ON oi.order_id = o.order_id
JOIN products_3nf p
    ON p.product_id = oi.product_id
WHERE o.order_id = 1;

EXPLAIN ANALYZE
SELECT
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount,
    c.customer_name,
    c.customer_email,
    p.product_name,
    oi.quantity,
    oi.price_at_order
FROM orders_3nf o
JOIN customers_3nf c
    ON c.customer_id = o.customer_id
JOIN order_items_3nf oi
    ON oi.order_id = o.order_id
JOIN products_3nf p
    ON p.product_id = oi.product_id
WHERE o.order_id = 1;

-- 4. Отчет "топ-10 товаров"
-- GROUP BY + ORDER BY + LIMIT

SELECT
    p.product_id,
    p.product_name,
    SUM(oi.quantity) AS total_sold
FROM order_items_3nf oi
JOIN products_3nf p
    ON p.product_id = oi.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_sold DESC
LIMIT 10;

EXPLAIN ANALYZE
SELECT
    p.product_id,
    p.product_name,
    SUM(oi.quantity) AS total_sold
FROM order_items_3nf oi
JOIN products_3nf p
    ON p.product_id = oi.product_id
GROUP BY p.product_id, p.product_name
ORDER BY total_sold DESC
LIMIT 10;

-- 5. Поиск клиента
-- 5.1 По email
-- 5.2 По подстроке имени

SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_email = 'client1@mail.ru';

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_email = 'client1@mail.ru';

SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';