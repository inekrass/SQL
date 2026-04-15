-- 4.1 Материализованное представление для отчётов

DROP MATERIALIZED VIEW IF EXISTS mv_monthly_sales;

-- 1. Создаем материализованное представление

CREATE MATERIALIZED VIEW mv_monthly_sales AS
SELECT
    date_trunc('month', o.order_date) AS month,
    p.product_name,
    c.category_name,
    SUM(oi.quantity) AS total_qty,
    SUM(oi.quantity * oi.price_at_order) AS total_revenue
FROM order_items_3nf oi
JOIN orders_3nf o ON o.order_id = oi.order_id
JOIN products_3nf p ON p.product_id = oi.product_id
JOIN categories c ON c.category_id = p.category_id
GROUP BY 1,2,3;

-- 2. Запрос к нормализованным таблицам

EXPLAIN ANALYZE
SELECT
    date_trunc('month', o.order_date) AS month,
    p.product_name,
    c.category_name,
    SUM(oi.quantity) AS total_qty,
    SUM(oi.quantity * oi.price_at_order) AS total_revenue
FROM order_items_3nf oi
JOIN orders_3nf o ON o.order_id = oi.order_id
JOIN products_3nf p ON p.product_id = oi.product_id
JOIN categories c ON c.category_id = p.category_id
GROUP BY 1,2,3;

-- 3. Запрос к материализованному представлению

EXPLAIN ANALYZE
SELECT *
FROM mv_monthly_sales;

-- 4. Обновление materialized view

REFRESH MATERIALIZED VIEW mv_monthly_sales;