CREATE DATABASE IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.orders_analytics (
    order_date Date,
    order_id UInt64,
    customer_name String,
    region LowCardinality(String),
    product_name String,
    category LowCardinality(String),
    quantity UInt32,
    price Decimal(12, 2),
    line_total Decimal(12, 2),
    order_status LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(order_date)
ORDER BY (category, order_date, order_id);
