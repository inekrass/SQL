#!/usr/bin/env sh
set -eu

echo "Prometheus targets:"
curl -sS "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22clickhouse%22%7D"
echo

echo "Rows metric:"
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables"
echo

echo "QPS metric:"
curl -sS "http://localhost:9090/api/v1/query?query=rate%28ClickHouseProfileEvents_Query%7Bjob%3D%22clickhouse%22%7D%5B5m%5D%29"
echo

echo "Replication metrics:"
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseMetrics_ReadonlyReplica"
echo
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseAsyncMetrics_ReplicasMaxQueueSize"
echo

echo "Memory metric:"
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseMetrics_MemoryTracking"
echo

echo "Grafana dashboard search:"
curl -sS -u admin:admin "http://localhost:3000/api/search?query=ClickHouse%20HA%20Cluster"
echo
