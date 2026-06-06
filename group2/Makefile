# Поднять основные сервисы для первых двух частей: PostgreSQL и ClickHouse.
up:
	docker compose up -d postgres clickhouse

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

# Остановить и удалить контейнеры проекта.
down:
	docker compose down
