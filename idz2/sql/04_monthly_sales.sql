CREATE TABLE idz2.monthly_sales
(
    month          Date,
    category       LowCardinality(String),
    region         LowCardinality(String),
    total_quantity UInt64,
    total_revenue  Decimal(14, 2)
)
ENGINE = SummingMergeTree()
ORDER BY (month, category, region);