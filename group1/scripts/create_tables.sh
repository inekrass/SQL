#!/usr/bin/env sh
set -eu

docker compose exec -T ch-s1-r1 clickhouse-client --multiquery < sql/01_create_tables.sql
