#!/usr/bin/env sh
set -eu

ROWS="${1:-5000000}"

docker compose exec -T ch-s1-r1 clickhouse-client --query "
INSERT INTO telemetry.metrics_distributed
SELECT
    now64(3) - toIntervalSecond(number % 86400) AS timestamp,
    concat('host-', toString(number % 100)) AS host,
    ['cpu_usage', 'memory_usage', 'disk_read', 'disk_write', 'network_in', 'network_out'][(number % 6) + 1] AS metric_name,
    round(randCanonical() * 100, 4) AS value
FROM numbers(${ROWS});
"
