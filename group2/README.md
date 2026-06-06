# Групповая работа 2. Multi-DB Pipeline: PostgreSQL + ClickHouse + ManticoreSearch

**Выполнил**: Некрасов Богдан<br>
**Группа**: Р4150<br>

## Часть 1. PostgreSQL — OLTP-ядро

В этой части развернут PostgreSQL как основная OLTP-БД интернет-магазина.
Сделана нормализованная схема в 3NF: отдельные таблицы для клиентов, категорий, товаров, заказов, позиций заказа и отзывов.

### Что добавлено

- `docker-compose.yml` - контейнер PostgreSQL 16.
- `.env.example` - пример переменных окружения для подключения и генерации данных.
- `sql/pg/01_schema.sql` - схема PostgreSQL:
  - `customers`
  - `categories`
  - `products`
  - `orders`
  - `order_items`
  - `reviews`
- `scripts/generate_data.py` - скрипт наполнения данными.
- `scripts/requirements.txt` - Python-зависимости для генератора.
- `sql/pg/03_oltp_queries.sql` - примеры типовых OLTP-операций.

### Как запустить PostgreSQL

```bash
cp .env.example .env
docker compose up -d postgres
```

При первом запуске PostgreSQL автоматически применяет файл `sql/pg/01_schema.sql`.

### Как наполнить данными

```bash
pip install -r scripts/requirements.txt
python3 scripts/generate_data.py
```

По умолчанию скрипт создает:

- 50 000 клиентов;
- 5 000 товаров;
- 500 000 заказов;
- не меньше 500 000 строк в `order_items`;
- 200 000 отзывов.

Количество можно поменять через переменные из `.env.example`.

### OLTP-операции

В файле `sql/pg/03_oltp_queries.sql` показаны типовые операции:

- создание заказа в транзакции;
- добавление позиций заказа;
- обновление статуса заказа;
- чтение заказа с JOIN-ами по клиенту, товарам и категориям;
- проверка количества строк в основных таблицах.

Запуск:

```bash
docker compose exec postgres psql -U shop_user -d shop -f /sql/pg/03_oltp_queries.sql
```

### Проверка таблиц в PostgreSQL

Зайти в `psql` внутри контейнера:

```bash
docker compose exec postgres psql -U shop_user -d shop
```

Cписок таблиц:

```bash
shop=# \dt
            List of relations
 Schema |    Name     | Type  |   Owner   
--------+-------------+-------+-----------
 public | categories  | table | shop_user
 public | customers   | table | shop_user
 public | order_items | table | shop_user
 public | orders      | table | shop_user
 public | products    | table | shop_user
 public | reviews     | table | shop_user
```


Проверить количество строк в основных таблицах:

```sql
SELECT 'customers' AS table_name, count(*) AS rows_count FROM customers
UNION ALL
SELECT 'categories', count(*) FROM categories
UNION ALL
SELECT 'products', count(*) FROM products
UNION ALL
SELECT 'orders', count(*) FROM orders
UNION ALL
SELECT 'order_items', count(*) FROM order_items
UNION ALL
SELECT 'reviews', count(*) FROM reviews;
```

Результат (уже после OLTP-операций):

```bash
 table_name  | rows_count 
-------------+------------
 categories  |         20
 products    |       5000
 customers   |      50000
 reviews     |     200000
 orders      |     500001
 order_items |    1000002
```

Проверить, что JOIN по заказу работает:

```sql
SELECT
    o.order_id,
    o.status,
    c.first_name || ' ' || c.last_name AS customer_name,
    p.name AS product_name,
    cat.name AS category_name,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_total
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN categories cat ON cat.category_id = p.category_id
ORDER BY o.order_id
LIMIT 10;
```

Результат:

```bash
 order_id |  status   |  customer_name   | product_name | category_name | quantity | unit_price | line_total 
----------+-----------+------------------+--------------+---------------+----------+------------+------------
        1 | paid      | Customer2 Testov | Product 3    | Category 4    |        3 |  112559.07 |  337677.21
        1 | paid      | Customer2 Testov | Product 4    | Category 5    |        4 |  111871.07 |  447484.28
        2 | shipped   | Customer3 Testov | Product 4    | Category 5    |        4 |   63158.15 |  252632.60
        2 | shipped   | Customer3 Testov | Product 5    | Category 6    |        5 |   65954.62 |  329773.10
        3 | delivered | Customer4 Testov | Product 5    | Category 6    |        5 |   47672.79 |  238363.95
        3 | delivered | Customer4 Testov | Product 6    | Category 7    |        1 |   43818.03 |   43818.03
        4 | cancelled | Customer5 Testov | Product 6    | Category 7    |        1 |    6624.64 |    6624.64
        4 | cancelled | Customer5 Testov | Product 7    | Category 8    |        2 |   60936.15 |  121872.30
        5 | new       | Customer6 Testov | Product 7    | Category 8    |        2 |   14043.03 |   28086.06
        5 | new       | Customer6 Testov | Product 8    | Category 9    |        3 |   41977.98 |  125933.94
```

Результаты проверок записаны в `checks/pg_oltp.txt`.

## Часть 2. ETL в ClickHouse

В этой части добавлен перенос данных из PostgreSQL в ClickHouse для аналитики.
Используется вариант A из задания: простой Python ETL-скрипт.

Скрипт:

- читает данные из PostgreSQL через `SELECT` с JOIN-ами;
- превращает нормализованные таблицы в плоскую денормализованную таблицу;
- пишет результат в ClickHouse.

### Что добавлено

- `clickhouse` в `docker-compose.yml` - контейнер ClickHouse.
- `sql/ch/01_tables.sql` - таблица `analytics.orders_analytics`.
- `sql/ch/03_analytics.sql` - аналитические запросы для проверки.
- `etl/pg_to_ch.py` - ETL-скрипт PostgreSQL -> ClickHouse.
- `Makefile` - команды для запуска и проверки.

### Как запустить ClickHouse

```bash
docker compose up -d clickhouse
```

При первом запуске ClickHouse применяет SQL-файлы из `sql/ch`.

Основная таблица:

```text
analytics.orders_analytics
```

Это плоская таблица для аналитики. В одной строке лежат дата заказа, заказ, клиент, регион, товар, категория, количество, цена, `line_total` и статус заказа.

`line_total` - это сумма позиции заказа: `quantity * price`.

### Как запустить ETL

PostgreSQL должен быть запущен и заполнен данными.

```bash
pip3 install -r scripts/requirements.txt
python3 etl/pg_to_ch.py
```

Или через Makefile:

```bash
make etl
```

### Как проверить ClickHouse

Проверить количество строк в аналитической таблице:

```bash
docker compose exec clickhouse clickhouse-client \
  --user analytics_user \
  --password analytics_password \
  --database analytics \
  --query "SELECT count(*) FROM analytics.orders_analytics"
```

Результат:
```bash
1000002
```

Вывод: количество строк в ClickHouse совпадает с количеством строк источника в PostgreSQL (источником является таблица `order_items`, так как в ClickHouse одна строка `orders_analytics` = одна строка из `order_items` + данные из связанных таблиц).

Запустить аналитические запросы:

```bash
docker compose exec clickhouse clickhouse-client \
  --user analytics_user \
  --password analytics_password \
  --database analytics \
  --queries-file /sql/ch/03_analytics.sql
```

Результаты проверки ETL и аналитических запросов в `checks/etl_sync.txt`.

В ходе проверки перенесено `1 000 002` строки из PostgreSQL в ClickHouse.
Количество строк в ClickHouse совпало с количеством строк в `order_items`.

## Часть 3. ManticoreSearch — поиск по отзывам

В этой части добавлен ManticoreSearch для полнотекстового поиска по отзывам.
PostgreSQL остается источником отзывов, а ManticoreSearch хранит RT-индекс `reviews`.

### Что добавлено

- `manticore` в `docker-compose.yml` - контейнер ManticoreSearch.
- `sql/manticore/01_create_index.sql` - создание RT-индекса `reviews`.
- `sql/manticore/02_search_queries.sql` - поисковые запросы для проверки.
- `etl/pg_to_manticore.py` - ETL-скрипт PostgreSQL -> ManticoreSearch.
- команды в `Makefile`:
  - `manticore-init`
  - `manticore-etl`
  - `manticore-check`

### Индекс reviews

Индекс содержит:

- `title` - заголовок отзыва;
- `body` - текст отзыва;
- `product_id` - товар;
- `customer_id` - клиент;
- `rating` - оценка;
- `created_at` - дата создания.

Создание индекса:

```bash
docker compose exec manticore mysql -h0 -P9306 < sql/manticore/01_create_index.sql
```

### Как загрузить отзывы

PostgreSQL должен быть запущен и заполнен отзывами.

```bash
python3 etl/pg_to_manticore.py
```

Скрипт читает отзывы из PostgreSQL и загружает их в индекс ManticoreSearch.

### Как проверить поиск

```bash
docker compose exec manticore mysql -h0 -P9306 < sql/manticore/02_search_queries.sql
```

В проверках есть:

- полнотекстовый поиск по отзывам;
- фильтр по `rating` и `product_id`;
- фасетный поиск по рейтингу;
- поиск негативных отзывов.

Реальные результаты проверки ManticoreSearch записываются в `checks/manticore_search.txt`.

В ходе проверки в ManticoreSearch загружено `200 001` отзывов.
Полнотекстовый поиск, фильтр по рейтингу/товару, фасеты и поиск негативных отзывов отработали успешно.

## Часть 4. Единая точка входа

В этой части добавлен demo-скрипт, который показывает общий сценарий работы системы.
Это не отдельная база и не API-сервер, а один Python-скрипт для демонстрации end-to-end потока.

### Что добавлено

- `scripts/demo_scenario.py` - demo-сценарий.
- команда `demo` в `Makefile`.

### Что делает demo-сценарий

Скрипт выполняет шаги из задания:

- создает заказ в PostgreSQL;
- запускает ETL PostgreSQL -> ClickHouse;
- выполняет аналитический запрос в ClickHouse: топ-5 категорий по выручке;
- добавляет отзыв в PostgreSQL;
- запускает синхронизацию PostgreSQL -> ManticoreSearch;
- выполняет полнотекстовый поиск в ManticoreSearch.

ETL в ClickHouse сейчас работает как full-refresh. При запуске demo таблица `analytics.orders_analytics` очищается и заново собирается из всех заказов PostgreSQL, а не догружает только новый заказ. Так же происходит и в Manticore.

Запуск:

```bash
python3 scripts/demo_scenario.py
```

Или через Makefile:

```bash
make demo
```

Реальный вывод demo-сценария записывается в `checks/demo_output.txt`.

В ходе проверки demo-сценарий создал заказ `500002`, загрузил `1 000 004` строки в ClickHouse, создал отзыв `200002` и загрузил `200 002` отзыва в ManticoreSearch.

## Часть 5. Мониторинг Grafana

В этой части добавлен мониторинг через Prometheus и Grafana.
Grafana поднимается с готовым datasource и dashboard через provisioning, то есть вручную в UI ничего создавать не нужно.

### Что добавлено

- `metrics-exporter` в `docker-compose.yml` - Python exporter, который собирает метрики из PostgreSQL, ClickHouse, ManticoreSearch и файла состояния pipeline.
- `prometheus` в `docker-compose.yml` - собирает метрики exporter-а.
- `grafana` в `docker-compose.yml` - показывает dashboard.
- `monitoring/metrics_exporter.py` - код exporter-а.
- `config/prometheus/prometheus.yml` - конфиг Prometheus.
- `monitoring/provisioning/datasources/prometheus.yml` - datasource Grafana.
- `monitoring/provisioning/dashboards/dashboards.yml` - provisioning dashboard-ов.
- `monitoring/dashboards/multi_db.json` - dashboard в JSON.

### Какие панели есть в dashboard

- PostgreSQL: активные подключения, транзакции/сек, размер таблиц.
- ClickHouse: строки в `orders_analytics`, запросы/сек, статус ClickHouse ноды.
- ManticoreSearch: количество документов, время поискового запроса.
- Pipeline: время последней синхронизации, количество обработанных записей.

### Как запустить мониторинг

Перед запуском мониторинга должны быть подняты PostgreSQL, ClickHouse и ManticoreSearch.

```bash
docker compose up -d metrics-exporter prometheus grafana
```

Или через Makefile:

```bash
make monitoring-up
```

Grafana будет доступна:

```text
http://localhost:3000
```

Логин и пароль по умолчанию:

```text
admin / admin
```

Dashboard называется:

```text
Multi-DB Pipeline Monitoring
```

Реальные результаты проверки мониторинга записываются в `checks/monitoring.txt`.

В ходе проверки Prometheus увидел target `metrics-exporter:9180` со статусом `up`, а Grafana создала dashboard `Multi-DB Pipeline Monitoring`.

## Часть 6. Сравнительный анализ

В этой части сделаны реальные замеры PostgreSQL, ClickHouse и ManticoreSearch на текущем проекте.
Для тестов использовались отдельные benchmark-таблицы, чтобы не портить основные данные проекта.

Результаты сохранены в `checks/comparison_table.txt`.

| Операция | PostgreSQL | ClickHouse | ManticoreSearch |
|---|---:|---:|---:|
| Вставка 1 записи | 0.28 ms | 3.12 ms | 0.63 ms |
| Вставка 100K записей | 236.91 ms | 127.69 ms | 1.28 sec |
| SELECT по PK | 0.31 ms | 2.31 ms | 1.15 ms |
| Аналитика GROUP BY | 104.19 ms | 14.30 ms | N/A |
| Полнотекстовый поиск | 0.42 ms | N/A | 4.35 ms |
| UPDATE 1 записи | 0.27 ms | не рекомендуется | 0.38 ms |
| Размер / footprint | 251.37 MB | 16.53 MB | 41.00 MB |

### Выводы

PostgreSQL лучше подходит для OLTP-задач: создание заказов, транзакции, UPDATE и чтение по ключу.

ClickHouse лучше подходит для аналитики. На `GROUP BY` по большой таблице он быстрее PostgreSQL, потому что хранит данные колонками и оптимизирован под агрегации.

ManticoreSearch лучше подходит для полнотекстового поиска и фасетов по отзывам. Это не замена PostgreSQL или ClickHouse, а отдельный поисковый движок.

В итоге системы решают разные задачи:

- PostgreSQL - хранит операционные данные интернет-магазина;
- ClickHouse - считает аналитику по заказам и выручке;
- ManticoreSearch - ищет по текстам отзывов.

Примечание по размеру:

- PostgreSQL: размер текущей базы через `pg_database_size`.
- ClickHouse: `bytes_on_disk` активных parts базы `analytics`.
- ManticoreSearch: учитываем и данные на диске, и данные в памяти, потому что часть индекса Manticore хранит прямо в RAM.
