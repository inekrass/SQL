-- Проверяем, сколько строк попало в ClickHouse после ETL.
SELECT count(*) AS rows_count
FROM analytics.orders_analytics;

-- Считаем топ-5 категорий по выручке.
-- Типичный OLAP-запрос: GROUP BY по категории и сортировка по сумме продаж.
SELECT
    category,
    sum(line_total) AS revenue
FROM analytics.orders_analytics
GROUP BY category
ORDER BY revenue DESC
LIMIT 5;

-- Считаем дневную динамику заказов.
-- По каждому дню показываем количество уникальных заказов и общую выручку.
SELECT
    order_date,
    countDistinct(order_id) AS orders_count,
    sum(line_total) AS revenue
FROM analytics.orders_analytics
GROUP BY order_date
ORDER BY order_date
LIMIT 10;
