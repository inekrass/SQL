CREATE TABLE IF NOT EXISTS user_dict ON CLUSTER cluster_2x2
(
    user_id UInt64,
    name String,
    segment LowCardinality(String)
)
ENGINE = ReplicatedMergeTree(
    '/clickhouse/tables/user_dict',
    '{replica}'
)
ORDER BY user_id;

INSERT INTO user_dict
SELECT
    toUInt64(number + 1) AS user_id,
    concat('user_', toString(number + 1)) AS name,
    arrayElement(
        ['new', 'regular', 'vip', 'inactive'],
        (number % 4) + 1
    ) AS segment
FROM numbers(100000);