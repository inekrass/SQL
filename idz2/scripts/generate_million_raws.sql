USE idz2;

INSERT INTO orders_flat
SELECT
    addDays(src.order_date, n.number % 365) AS order_date,
    src.order_datetime + toIntervalHour(n.number % 24) AS order_datetime,
    src.order_id + (n.number + 1) * 1000000 AS order_id,
    src.customer_id + (n.number + 1) * 1000000 AS customer_id,
    concat(src.customer_name, ' copy ', toString(n.number + 1)) AS customer_name,
    concat('copy', toString(n.number + 1), '_', src.customer_email) AS customer_email,
    src.region,
    src.product_id,
    src.product_name,
    src.category,
    src.quantity,
    src.price,
    src.line_total,
    src.order_status
FROM
(
    SELECT *
    FROM orders_flat
    ORDER BY order_id, product_id
) AS src
CROSS JOIN numbers(428) AS n
LIMIT 997665;