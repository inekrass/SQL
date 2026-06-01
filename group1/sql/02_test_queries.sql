SELECT cluster, shard_num, replica_num, host_name
FROM system.clusters
WHERE cluster = 'production'
ORDER BY shard_num, replica_num;

SELECT count() AS total_rows
FROM telemetry.metrics_distributed;

SELECT _shard_num, count() AS rows_on_shard
FROM telemetry.metrics_distributed
GROUP BY _shard_num
ORDER BY _shard_num;

SELECT hostName() AS host, count() AS local_rows
FROM clusterAllReplicas('production', telemetry, metrics_local)
GROUP BY host
ORDER BY host;

SELECT
    hostName() AS host,
    database,
    table,
    replica_name,
    is_leader,
    is_readonly,
    absolute_delay,
    queue_size
FROM clusterAllReplicas('production', system, replicas)
WHERE database = 'telemetry' AND table = 'metrics_local'
ORDER BY host;

SELECT
    metric_name,
    count() AS rows_count,
    round(avg(value), 2) AS avg_value
FROM telemetry.metrics_distributed
GROUP BY metric_name
ORDER BY metric_name;
