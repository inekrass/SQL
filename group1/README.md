# Групповая работа 1. HA-кластер ClickHouse 2x2 с мониторингом и балансировкой

**Выполнил**: Некрасов Богдан<br>
**Группа**: Р4150<br>

## Часть 1. Инфраструктура

Добавлен каркас Docker Compose для 10 сервисов:

- 4 ClickHouse-ноды: `ch-s1-r1`, `ch-s1-r2`, `ch-s2-r1`, `ch-s2-r2`;
- 3 ClickHouse Keeper-ноды: `keeper-1`, `keeper-2`, `keeper-3`;
- `nginx`, `prometheus`, `grafana`.

Конфигурация вынесена в каталоги `config/` и `monitoring/provisioning/`.
Общие настройки сервисов в `docker-compose.yml` вынесены через `x-clickhouse-common` и `x-keeper-common`.

Основные команды:

```bash
make up
make status
make test
make down
```

## Часть 2. ClickHouse-кластер

Добавлена конфигурация кластера `production`: 2 шарда x 2 реплики.
Keeper используется для репликации и DDL-запросов `ON CLUSTER`.

Что добавлено:

- `config/clickhouse/config.d/cluster.xml` — описание кластера `production`, Keeper и макросов `{shard}` / `{replica}`;
- `config/clickhouse/users.d/default-user.xml` — доступ пользователя `default` между контейнерами;
- `sql/01_create_tables.sql` — создание БД и таблиц `ON CLUSTER production`;
- `sql/02_test_queries.sql` — SQL-проверки кластера, строк, шардов и реплик;
- `scripts/create_tables.sh` — создание таблиц;
- `scripts/generate_data.sh` — генерация тестовых данных;
- `scripts/check_cluster.sh` — запуск проверочных SQL-запросов;
- `checks/*.txt` — сохраненные результаты проверок.

Таблицы:

- `telemetry.metrics_local` — локальная таблица, где данные реально физически лежат на ClickHouse-нодах на `ReplicatedMergeTree`;
- `telemetry.metrics_distributed` — распределенная таблица `Distributed` поверх `metrics_local`. Она нужна, чтобы обращаться ко всему кластеру как к одной таблице.

Схема данных:

```text
timestamp DateTime64(3)
host LowCardinality(String)
metric_name LowCardinality(String)
value Float64
```

Команды этапа:

```bash
make up
make create-tables
make generate-data
make check-cluster
```

`make generate-data` по умолчанию вставляет `5 000 000` строк тестовой телеметрии через `telemetry.metrics_distributed`.

Проверки:

- `docker compose ps` — все 10 контейнеров находятся в статусе `Up`;
- `system.clusters` — в кластере `production` видны 2 шарда и 4 реплики;
- `count()` через `telemetry.metrics_distributed` — возвращает `5 000 000` строк;
- группировка по `_shard_num` — показывает распределение данных по шардам;
- `clusterAllReplicas(..., telemetry.metrics_local)` — показывает одинаковое количество строк на репликах одного шарда;
- `clusterAllReplicas(..., system.replicas)` — показывает состояние репликации;
- агрегирующий запрос через `metrics_distributed` возвращает корректный результат по всем метрикам.

Результат проверки:

- всего строк: `5 000 000`;
- распределение по шардам:

```text
shard 1: 2 500 145
shard 2: 2 499 855
```

- строки на локальных репликах:

```text
ch-s1-r1: 2 500 145
ch-s1-r2: 2 500 145
ch-s2-r1: 2 499 855
ch-s2-r2: 2 499 855
```

- состояние реплик:

```text
is_readonly = 0 #Реплика не в read-only режиме. То есть она может принимать записи и нормально работать.
absolute_delay = 0 #Нет задержки репликации. Реплика не отстает от остальных.
queue_size = 0 #Очередь репликации пустая. Реплике не осталось задач, которые надо догнать.
```

- результата запроса через `metrics_distributed`, который работает корректно и читает данные со всего кластера:

```text
Query through telemetry.metrics_distributed:
название метрики | количество строк | среднее значение
cpu_usage	       833334	           50.03
disk_read	       833333	           50.02
disk_write	       833333	           49.99
memory_usage	   833334	           50
network_in	       833333	           49.98
network_out	       833333	           49.99
```
То есть строки у нас распределились по всем 6 метрикам равномерно (`5 000 000 / 6 = 833333`). А среднее значение около 50, так как мы случайно генерировали данные в диапазоне от 0 до 100.

## Часть 3. Nginx как HTTP-балансировщик

Nginx проксирует HTTP-интерфейс ClickHouse на порт `8123`.
Upstream `clickhouse_http` содержит 4 ClickHouse-ноды:

```text
ch-s1-r1:8123
ch-s1-r2:8123
ch-s2-r1:8123
ch-s2-r2:8123
```

`upstream` — это группа backend-серверов, между которыми Nginx распределяет запросы.
В нашем случае backend-серверы — это 4 ClickHouse-ноды.

`round-robin` — стандартный алгоритм балансировки Nginx: запросы отправляются на серверы по очереди.
Например: первый запрос на `ch-s1-r1`, второй на `ch-s1-r2`, третий на `ch-s2-r1`, четвертый на `ch-s2-r2`, затем снова по кругу.

Что добавлено:

- `config/nginx/nginx.conf` — upstream на 4 ClickHouse-ноды;
- round-robin балансировка между узлами;
- passive health checks через `max_fails=2` и `fail_timeout=10s`;
```
Passive health checks — это когда Nginx сам не ходит заранее проверять “жив ли сервер”, а делает вывод по реальным запросам.

У нас это здесь:

server ch-s1-r2:8123 max_fails=2 fail_timeout=10s;
Значит:

 - если запросы к ch-s1-r2 начали падать;
 - Nginx считает ошибки;
 - после max_fails=2 ошибок;
 - он временно исключает эту ноду из балансировки на fail_timeout=10s.
```

- `proxy_next_upstream` — повтор запроса на другой узел при ошибке;
- JSON access-log с `upstream_addr`, `upstream_status`, `request_time`;
- `scripts/check_nginx.sh` — проверочный запрос через Nginx;
- В Makefile `make check-nginx` и `make nginx-logs`.

Что описали в `config/nginx/nginx.conf`:

- `log_format json_combined ...` — формат access-лога в JSON;
- `access_log /var/log/nginx/access.log json_combined` — запись запросов в JSON-логе;
- `upstream clickhouse_http { ... }` — список 4 ClickHouse backend-нод;
- `server ch-...:8123 max_fails=2 fail_timeout=10s` — параметры passive health check: после ошибок Nginx временно исключает узел;
- `server { listen 8123; ... }` — Nginx слушает порт `8123`;
- `location / { proxy_pass http://clickhouse_http; }` — все HTTP-запросы отправляются в upstream ClickHouse;
- `proxy_next_upstream error timeout http_500 http_502 http_503 http_504` — при ошибке Nginx пробует другой upstream;

Проверочный запрос из `scripts/check_nginx.sh`:

```bash
curl -sS --data-binary "SELECT hostName() AS node" "http://localhost:8123/"
```

Этот запрос идет не напрямую в ClickHouse-контейнер, а через Nginx.
ClickHouse возвращает имя ноды, которая реально обработала запрос.

Команды проверки:

```bash
make up
make check-nginx
docker compose stop ch-s1-r2
make check-nginx
docker compose start ch-s1-r2
make nginx-logs
```

Шаги проверки:

1. Подняли стек командой `make up`.
2. Выполнили несколько запросов `make check-nginx`.
3. По ответам `hostName()` убедились, что запросы попадают на разные ClickHouse-ноды.
4. Остановили одну ноду: `docker compose stop ch-s1-r2`.
5. Повторили `make check-nginx`.
6. Убедились, что запросы продолжают выполняться через оставшиеся ноды.
7. Восстановили ноду: `docker compose start ch-s1-r2`.
8. Посмотрели логи Nginx командой `make nginx-logs`.

Что проверяется:

- запросы идут через `http://localhost:8123`;
- Nginx проксирует запросы в ClickHouse HTTP API;
- при остановке одной CH-ноды запросы продолжают выполняться;
- в access-логе есть JSON-записи с адресом upstream-ноды.

Результат проверки round-robin:

```text
ch-s1-r2
ch-s2-r1
ch-s2-r2
ch-s1-r1
ch-s1-r2
ch-s2-r1
ch-s2-r2
ch-s1-r1
```

Результат после остановки `ch-s1-r2`:

```text
ch-s2-r1
ch-s2-r2
ch-s2-r1
ch-s1-r1
ch-s2-r2
ch-s2-r1
ch-s1-r1
ch-s2-r2
```

JSON access-лог при failover:

```json
{"status":200,"upstream_addr":"172.22.0.8:8123, 172.22.0.10:8123","upstream_status":"504, 200","upstream_response_time":"2.003, 0.011"}
```

Расшифровка:

- `status: 200` — клиент получил успешный ответ;
- `upstream_addr: "172.22.0.8:8123, 172.22.0.10:8123"` — Nginx попробовал две upstream-ноды;
- `upstream_status: "504, 200"` — первая попытка не удалась, вторая прошла успешно;
- `upstream_response_time` — время ответа по каждой попытке.

Итог: при остановке одной ClickHouse-ноды запросы через Nginx продолжили работать, Nginx переключил запрос на доступный upstream.

## Часть 4. Мониторинг

Prometheus собирает метрики ClickHouse через встроенный endpoint `/metrics`.
Endpoint включен в `config/clickhouse/config.d/prometheus.xml`, порт метрик — `9363`.

Prometheus — это система мониторинга. Он сам периодически ходит по HTTP endpoint-ам сервисов, забирает числовые метрики и хранит их как time series.
В этом проекте Prometheus ходит на `/metrics` каждой ClickHouse-ноды и сохраняет метрики по строкам, запросам, репликации и памяти.

Grafana — это система визуализации. Она не собирает метрики сама, а подключается к datasource, в нашем случае к Prometheus, и строит dashboard по PromQL-запросам.

Что добавлено:

- `config/prometheus/prometheus.yml` — scrape targets для 4 ClickHouse-нод;
- `monitoring/provisioning/datasources/datasources.yml` — автоматическое добавление Prometheus datasource в Grafana;
- `monitoring/provisioning/dashboards/dashboards.yml` — автоматическая загрузка dashboard из каталога;
- `monitoring/dashboards/clickhouse.json` — JSON dashboard в формате Grafana; Dashboard подготовлен в формате JSON. Grafana автоматически подхватывает его через provisioning.
- `scripts/check_monitoring.sh` — проверка Prometheus targets, PromQL-метрик и Grafana dashboard;
- В Makefile `make check-monitoring`.

`monitoring/provisioning/dashboards/dashboards.yml`:

Это конфиг Grafana. Он говорит Grafana искать JSON dashboard-файлы в каталоге:

```yaml
path: /var/lib/grafana/dashboards
```

Поэтому dashboard из `monitoring/dashboards/clickhouse.json` появляется в Grafana автоматически при старте.

Dashboard JSON:

Файл `monitoring/dashboards/clickhouse.json` подготовлен сразу как JSON.
Обычно такой файл можно получить через UI Grafana: Dashboard -> Share/Export -> Export JSON.
В этом проекте dashboard не импортировался вручную через UI, а лежит в репозитории как готовый JSON и подхватывается через provisioning.

Prometheus targets мы указали в `config/clickhouse/config.d/prometheus.xml`:

```text
ch-s1-r1:9363
ch-s1-r2:9363
ch-s2-r1:9363
ch-s2-r2:9363
```

Панели Grafana dashboard:

- `Rows In MergeTree Tables` — количество строк в MergeTree-таблицах через `ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables`;
- `Queries Per Second` — количество запросов в секунду через `rate(ClickHouseProfileEvents_Query[5m])`;
- `Readonly Replicas` — статус read-only реплик через `ClickHouseMetrics_ReadonlyReplica`;
- `Replication Queue Size` — очередь репликации;
- `Memory Usage` — использование памяти.

Команды проверки:

```bash
make up
make check-monitoring
```

Команда `make check-monitoring` запускает `scripts/check_monitoring.sh`.
Скрипт делает HTTP-запросы к Prometheus API и Grafana API через `curl`.

Проверка Prometheus targets:

```bash
curl -sS "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22clickhouse%22%7D"
```

Результаты проверки:

```text
ch-s1-r1:9363 up=1
ch-s1-r2:9363 up=1
ch-s2-r1:9363 up=1
ch-s2-r2:9363 up=1
```

Проверка метрик для dashboard:

```bash
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables" #cколько строк видит ClickHouse в MergeTree-таблицах на каждой ноде;
curl -sS "http://localhost:9090/api/v1/query?query=rate%28ClickHouseProfileEvents_Query%7Bjob%3D%22clickhouse%22%7D%5B5m%5D%29" #сколько запросов в секунду выполнялось за последние 5 минут;
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseMetrics_ReadonlyReplica" #находится ли реплика в read-only режиме;
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseAsyncMetrics_ReplicasMaxQueueSize" #максимальный размер очереди репликации;
curl -sS "http://localhost:9090/api/v1/query?query=ClickHouseMetrics_MemoryTracking" #текущее потребление памяти ClickHouse
```

Фактические результаты Prometheus-запросов:

```text
ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables:
ch-s1-r1: 15 568 363
ch-s1-r2: 15 527 235
ch-s2-r1: 15 560 726
ch-s2-r2: 15 552 241
```

```text
rate(ClickHouseProfileEvents_Query[5m]):
ch-s1-r1: 0
ch-s1-r2: 0
ch-s2-r1: 0
ch-s2-r2: 0
```

```text
ClickHouseMetrics_ReadonlyReplica:
ch-s1-r1: 0
ch-s1-r2: 0
ch-s2-r1: 0
ch-s2-r2: 0
```

`0` означает, что реплики не находятся в read-only режиме.

```text
ClickHouseAsyncMetrics_ReplicasMaxQueueSize:
ch-s1-r1: 0
ch-s1-r2: 0
ch-s2-r1: 0
ch-s2-r2: 0
```

`0` означает, что очередь репликации пустая и реплики не отстают.

```text
ClickHouseMetrics_MemoryTracking:
ch-s1-r1: 210 135 823 bytes
ch-s1-r2: 199 288 034 bytes
ch-s2-r1: 194 509 220 bytes
ch-s2-r2: 206 088 743 bytes
```

Проверка dashboard в Grafana:

```bash
curl -sS -u admin:admin "http://localhost:3000/api/search?query=ClickHouse%20HA%20Cluster"
```

Grafana API нашел dashboard с названием `ClickHouse HA Cluster`:

```text
uid=clickhouse-ha-cluster
title=ClickHouse HA Cluster
folder=ClickHouse
```

Что проверяется:

- Prometheus видит все 4 ClickHouse target в статусе `up`;
- PromQL-запросы для dashboard возвращают данные через Prometheus API;
- - Grafana datasource `Prometheus` создан через provisioning-файл `monitoring/provisioning/datasources/datasources.yml`;
- dashboard `ClickHouse HA Cluster` подтягивается из `monitoring/dashboards/clickhouse.json`.


Итог: Prometheus собирает метрики со всех ClickHouse-нод, Grafana автоматически получает datasource и dashboard через provisioning.

## Часть 5. Отказоустойчивость

Проведены fault injection сценарии: остановка реплики, остановка шарда, потеря одного Keeper и потеря quorum Keeper.
Команды и результаты сохранены в `checks/fault_scenarios.txt`.

Добавлено:

- `scripts/fault_injection.sh` — команды для остановки и восстановления сервисов по сценариям;
- `checks/fault_scenarios.txt` — выводы команд, результаты и восстановление;
- В Makefile `make fault-status` — быстрый статус сервисов.

Базовое состояние перед проверками:

```bash
docker compose ps
docker compose exec -T ch-s1-r1 clickhouse-client --query "SELECT count() FROM telemetry.metrics_distributed"
```

Результат:

```text
все 10 сервисов Up
count() = 10 000 000
```

### Потеря реплики

Команды:

```bash
docker compose stop ch-s1-r2
sh scripts/check_nginx.sh
docker compose exec -T ch-s1-r1 clickhouse-client --query "SELECT count() FROM telemetry.metrics_distributed"
docker compose start ch-s1-r2
```

Результат:

```text
sh scripts/check_nginx.sh -> ch-s2-r1
SELECT count() -> 10 000 000
```

Итог: при потере одной реплики запросы продолжают работать. Nginx отправляет запросы на доступные узлы, а `Distributed`-таблица читает shard через оставшуюся реплику.

### Потеря шарда

Команды:

```bash
docker compose stop ch-s2-r1 ch-s2-r2
docker compose exec -T ch-s1-r1 clickhouse-client --query "SELECT hostName()"
docker compose exec -T ch-s1-r1 clickhouse-client --connect_timeout 2 --receive_timeout 5 --send_timeout 5 --query "SELECT count() FROM telemetry.metrics_distributed"
docker compose start ch-s2-r1 ch-s2-r2
```

Результат:

```text
SELECT hostName() -> ch-s1-r1
SELECT count() FROM telemetry.metrics_distributed -> ALL_CONNECTION_TRIES_FAILED
```

Итог: shard 1 остается доступен, но запрос через `metrics_distributed` падает, потому что все реплики shard 2 недоступны.

### Потеря одного Keeper

Команды:

```bash
docker compose stop keeper-1
docker compose exec -T ch-s1-r1 clickhouse-client --query "INSERT INTO telemetry.metrics_distributed SELECT now64(3), 'fault-host', 'keeper_one_down', toFloat64(number) FROM numbers(10)" #добавляем 10 тестовых строк в распределенную таблицу
docker compose exec -T ch-s1-r1 clickhouse-client --query "SELECT count() FROM telemetry.metrics_distributed WHERE metric_name='keeper_one_down'" #пытаемся получить эти тестовые данные с пометкой "keeper_one_down"
docker compose start keeper-1
```

Результат:

```text
INSERT completed successfully
SELECT count() WHERE metric_name='keeper_one_down' -> 10
```

Итог: при потере одного Keeper quorum сохраняется, потому что `keeper-2` и `keeper-3` работают. Запись продолжает работать. Кворум сохраняется так как его формула floor(n/2)+1 (floor - это округление вниз). Здесь при 3-х участниках кворум будет жить при минимум 2 живых нод (3/2+1=2)

### Потеря quorum Keeper

Команды:

```bash
docker compose stop keeper-1 keeper-2
docker compose exec -T ch-s1-r1 clickhouse-client --receive_timeout 5 --send_timeout 5 --query "SELECT count() FROM telemetry.metrics_distributed"
docker compose exec -T ch-s1-r1 clickhouse-client --receive_timeout 5 --send_timeout 5 --query "INSERT INTO telemetry.metrics_distributed SELECT now64(3), 'fault-host', 'keeper_quorum_lost', toFloat64(number) FROM numbers(1)" #пытаемся добавить 1 тестовую строку в распределенную таблицу
docker compose start keeper-1 keeper-2
```

Результат:

```text
SELECT count() -> 10 000 010
INSERT did not complete while quorum was unavailable
after Keeper restore: TABLE_IS_READ_ONLY
```

Итог: чтение существующих данных работает, но запись невозможна без quorum Keeper.

Финальная проверка восстановления:

```bash
docker compose exec -T ch-s1-r1 clickhouse-client --query "SELECT hostName(), replica_name, is_readonly, absolute_delay, queue_size FROM clusterAllReplicas('production', system, replicas) WHERE database='telemetry' AND table='metrics_local' ORDER BY hostName()"
docker compose ps
```

Результат:

```text
ch-s1-r1 ch-s1-r1 0 0 0
ch-s1-r2 ch-s1-r2 0 0 0
ch-s2-r1 ch-s2-r1 0 0 0
ch-s2-r2 ch-s2-r2 0 0 0
все 10 сервисов Up
```
