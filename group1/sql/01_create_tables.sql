CREATE DATABASE IF NOT EXISTS telemetry ON CLUSTER production;

CREATE TABLE IF NOT EXISTS telemetry.metrics_local ON CLUSTER production
(
    timestamp DateTime64(3),
    host LowCardinality(String),
    metric_name LowCardinality(String),
    value Float64
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/telemetry/metrics_local', '{replica}')
PARTITION BY toYYYYMM(timestamp)
ORDER BY (metric_name, host, timestamp);

CREATE TABLE IF NOT EXISTS telemetry.metrics_distributed ON CLUSTER production
AS telemetry.metrics_local
ENGINE = Distributed(production, telemetry, metrics_local, rand());
