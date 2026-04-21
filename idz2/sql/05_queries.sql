USE idz2;

TRUNCATE TABLE monthly_sales;

-- Заполняем таблицу monthly_sales

INSERT INTO monthly_sales
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    region,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category,
    region;


-- 1. Топ-10 товаров по выручке
SELECT
    product_id,
    product_name,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    product_id,
    product_name
ORDER BY total_revenue DESC
LIMIT 10;


-- 2. Ежемесячная динамика продаж по категориям
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category
ORDER BY
    month,
    category;


-- 3. Процентиль p95/p99 стоимости заказа
-- Сначала считаем сумму заказа, потом берём процентиль
SELECT
    quantileExact(0.95)(order_total) AS p95_order_value,
    quantileExact(0.99)(order_total) AS p99_order_value
FROM
(
    SELECT
        order_id,
        sum(line_total) AS order_total
    FROM orders_flat
    GROUP BY order_id
);


-- 4. Поиск клиента по подстроке email
SELECT
    customer_id,
    customer_name,
    customer_email
FROM orders_flat
WHERE positionCaseInsensitive(customer_email, 'mail') > 0
GROUP BY
    customer_id,
    customer_name,
    customer_email
ORDER BY customer_id
LIMIT 20;


-- 5a. Агрегат напрямую из orders_flat
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    region,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category,
    region
ORDER BY
    month,
    category,
    region;


-- 5b. Тот же результат из monthly_sales
SELECT
    month,
    category,
    region,
    sum(total_quantity) AS total_quantity,
    sum(total_revenue) AS total_revenue
FROM monthly_sales
GROUP BY
    month,
    category,
    region
ORDER BY
    month,
    category,
    region;