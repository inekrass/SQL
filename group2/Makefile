# Поднять основные сервисы проекта: PostgreSQL, ClickHouse и ManticoreSearch.
up:
	docker compose up -d postgres clickhouse manticore

# Заполнить PostgreSQL тестовыми данными: клиенты, товары, заказы, отзывы.
pg-seed:
	python3 scripts/generate_data.py

# Запустить ETL PostgreSQL -> ClickHouse.
# Скрипт читает заказы из PostgreSQL и загружает плоскую таблицу orders_analytics.
etl:
	python3 etl/pg_to_ch.py

# Выполнить проверочные аналитические запросы в ClickHouse.
ch-check:
	docker compose exec clickhouse clickhouse-client \
		--user analytics_user \
		--password analytics_password \
		--database analytics \
		--queries-file /sql/ch/03_analytics.sql

# Создать RT-индекс reviews в ManticoreSearch.
manticore-init:
	docker compose exec -T manticore mysql -h0 -P9306 < sql/manticore/01_create_index.sql

# Загрузить отзывы из PostgreSQL в ManticoreSearch.
manticore-etl:
	python3 etl/pg_to_manticore.py

# Выполнить поисковые запросы по отзывам в ManticoreSearch.
manticore-check:
	docker compose exec -T manticore mysql -h0 -P9306 < sql/manticore/02_search_queries.sql

# Запустить end-to-end демо: PostgreSQL -> ClickHouse -> ManticoreSearch.
demo:
	python3 scripts/demo_scenario.py

# Поднять мониторинг: exporter, Prometheus и Grafana.
monitoring-up:
	docker compose up -d metrics-exporter prometheus grafana

# Проверить, что Prometheus видит exporter.
monitoring-check:
	docker compose exec prometheus wget -qO- http://metrics-exporter:9180/metrics

# Запустить сравнительные замеры PostgreSQL, ClickHouse и ManticoreSearch.
compare:
	python3 scripts/compare_systems.py

# Остановить и удалить контейнеры проекта.
down:
	docker compose down
