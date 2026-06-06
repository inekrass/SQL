import json
import os
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import clickhouse_connect
import psycopg2
import pymysql


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STATE_PATH = PROJECT_ROOT / "monitoring" / "pipeline_state.json"
EXPORTER_PORT = int(os.getenv("METRICS_EXPORTER_PORT", "9180"))


def pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "shop"),
        user=os.getenv("POSTGRES_USER", "shop_user"),
        password=os.getenv("POSTGRES_PASSWORD", "shop_password"),
    )


def ch_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "analytics_user"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "analytics_password"),
        database=os.getenv("CLICKHOUSE_DB", "analytics"),
    )


def ch_scalar(client, query):
    result = client.query(query)
    return result.result_rows[0][0]


def manticore_connection():
    return pymysql.connect(
        host=os.getenv("MANTICORE_HOST", "manticore"),
        port=int(os.getenv("MANTICORE_SQL_PORT", "9306")),
        user="",
        password="",
        database="",
        charset="utf8mb4",
        autocommit=True,
    )


def metric(name, value, labels=None):
    if labels:
        label_text = ",".join(f'{key}="{value}"' for key, value in labels.items())
        return f"{name}{{{label_text}}} {value}"
    return f"{name} {value}"


def collect_postgres_metrics():
    lines = []
    try:
        with pg_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity;")
                lines.append(metric("pg_active_connections", cursor.fetchone()[0]))

                cursor.execute(
                    """
                    SELECT xact_commit + xact_rollback
                    FROM pg_stat_database
                    WHERE datname = current_database();
                    """
                )
                lines.append(metric("pg_transactions_total", cursor.fetchone()[0]))

                cursor.execute(
                    """
                    SELECT relname, pg_total_relation_size(relid)
                    FROM pg_catalog.pg_statio_user_tables;
                    """
                )
                for table_name, table_size in cursor.fetchall():
                    lines.append(metric("pg_table_size_bytes", table_size, {"table": table_name}))
    except Exception as error:
        lines.append(metric("pg_exporter_up", 0))
        lines.append(f'# pg_error "{str(error)}"')
    else:
        lines.append(metric("pg_exporter_up", 1))

    return lines


def collect_clickhouse_metrics():
    lines = []
    try:
        client = ch_client()
        rows_count = ch_scalar(client, "SELECT count(*) FROM analytics.orders_analytics")
        lines.append(metric("clickhouse_orders_analytics_rows", rows_count))

        query_total = ch_scalar(client, "SELECT value FROM system.events WHERE event = 'Query'")
        lines.append(metric("clickhouse_queries_total", query_total))

        lines.append(metric("clickhouse_replication_status", 1, {"status": "single_node_no_replication"}))
    except Exception as error:
        lines.append(metric("clickhouse_exporter_up", 0))
        lines.append(f'# clickhouse_error "{str(error)}"')
    else:
        lines.append(metric("clickhouse_exporter_up", 1))

    return lines


def collect_manticore_metrics():
    lines = []
    try:
        with manticore_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM reviews")
                lines.append(metric("manticore_reviews_documents", cursor.fetchone()[0]))

                started_at = time.perf_counter()
                cursor.execute("SELECT id FROM reviews WHERE MATCH('kachestvo sborki') LIMIT 10")
                cursor.fetchall()
                elapsed = time.perf_counter() - started_at
                lines.append(metric("manticore_last_search_seconds", f"{elapsed:.6f}"))
    except Exception as error:
        lines.append(metric("manticore_exporter_up", 0))
        lines.append(f'# manticore_error "{str(error)}"')
    else:
        lines.append(metric("manticore_exporter_up", 1))

    return lines


def collect_pipeline_metrics():
    lines = []
    if not PIPELINE_STATE_PATH.exists():
        lines.append(metric("pipeline_state_file_exists", 0))
        return lines

    with PIPELINE_STATE_PATH.open("r", encoding="utf-8") as state_file:
        state = json.load(state_file)

    lines.append(metric("pipeline_state_file_exists", 1))
    for target, values in state.items():
        last_sync = values.get("last_sync_at")
        processed_records = values.get("processed_records", 0)
        if last_sync:
            sync_timestamp = datetime.fromisoformat(last_sync).timestamp()
            lines.append(metric("pipeline_last_sync_timestamp_seconds", sync_timestamp, {"target": target}))
        lines.append(metric("pipeline_processed_records", processed_records, {"target": target}))

    return lines


def collect_metrics():
    lines = [
        "# HELP pg_active_connections Active PostgreSQL connections.",
        "# TYPE pg_active_connections gauge",
        "# HELP clickhouse_orders_analytics_rows Rows in ClickHouse orders_analytics.",
        "# TYPE clickhouse_orders_analytics_rows gauge",
        "# HELP manticore_reviews_documents Documents in Manticore reviews index.",
        "# TYPE manticore_reviews_documents gauge",
        "# HELP pipeline_processed_records Last processed records count by pipeline target.",
        "# TYPE pipeline_processed_records gauge",
    ]
    lines.extend(collect_postgres_metrics())
    lines.extend(collect_clickhouse_metrics())
    lines.extend(collect_manticore_metrics())
    lines.extend(collect_pipeline_metrics())
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return

        payload = collect_metrics().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    print(f"metrics exporter started on 0.0.0.0:{EXPORTER_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
