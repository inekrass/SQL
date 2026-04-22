INSERT INTO idz2.orders_ttl
SELECT
    toDate('2024-01-01') AS order_date,
    toDateTime('2024-01-01 10:00:00') AS order_datetime,
    100000 + number AS order_id,
    5000 + number AS customer_id,
    concat('TTL Клиент ', toString(number)) AS customer_name,
    concat('ttl', toString(number), '@test.com') AS customer_email,
    'TTL Region' AS region,
    100 + number AS product_id,
    concat('TTL Product ', toString(number)) AS product_name,
    'TTL Category' AS category,
    1 AS quantity,
    toDecimal32(1000, 2) AS price,
    toDecimal32(1000, 2) AS line_total,
    'delivered' AS order_status
FROM numbers(1000)