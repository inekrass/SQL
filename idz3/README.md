# ИДЗ-3. Репликация в ClickHouse

**Выполнил**: Некрасов Богдан<br>
**Группа**: Р4150<br>
**ClickHouse**: 24.8.14.39

## Часть 1 - ClickHouse Keeper

1. Создаем три контейнера: keeper1, keeper2, keeper3.

Для каждого конфиг прописан в соответствующих файлах в ```config/keeper```

Каждому узлу дали уникальный ```server_id```:
```
keeper1 - server_id = 1
keeper2 - server_id = 2
keeper3 - server_id = 3
```

Внутри контейнеров Keeper использует порт 9181, а для проверки с хоста порты проброшены так:
```
keeper1 - localhost:9181
keeper2 - localhost:9182
keeper3 - localhost:9183
```

Обоснование топологии: 

Keeper использует кворум. Для трёх узлов большинство — это 2 из 3.
Поэтому кластер может пережить отказ одного Keeper-узла и продолжить работу.
Если остаётся только 1 из 3, кворум теряется, и записи в ```ReplicatedMergeTree``` перестают выполняться. 

Это дальше будет доказано экспериментом B.

2. Проверяем здоровье и состояние кворума:
```bash
echo ruok | nc localhost 9181
echo ruok | nc localhost 9182
echo ruok | nc localhost 9183

echo mntr | nc localhost 9181
echo mntr | nc localhost 9182
echo mntr | nc localhost 9183
```

Все контейнеры выдали ```imok```. А из результатов команды ```mntr``` видно что keeper1 получил роль ```leader```, а остальные ```follower```.

Результаты проверки всех трёх Keeper-узлов сохранены в файл: ```checks/keeper_health.txt```

## Часть 2 - Реплицированные таблицы

1. Добавляем 3 ClickHouse-узла
2. Настраиваем кластер:

- company_cluster — имя кластера
- 1 shard — один шард
- 3 replica — три реплики

3. Создаем макросы для каждого узла.

Макросы нужны, чтобы один и тот же SQL на каждом узле подставлял разное имя реплики.:
```sql
ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
```
Проверяем что ClickHouse видит кластер:
```bash
docker exec clickhouse1 clickhouse-client --query "SELECT cluster, shard_num, replica_num, host_name FROM system.clusters
WHERE cluster = 'company_cluster'"
---
company_cluster 1       1       clickhouse1
company_cluster 1       2       clickhouse2
company_cluster 1       3       clickhouse3
```

4. Создаем таблицу ```events``` на кластере:

```sql
CREATE TABLE IF NOT EXISTS events ON CLUSTER company_cluster
(
    event_time DateTime,
    event_type LowCardinality(String),
    user_id UInt64,
    payload String
)
ENGINE = ReplicatedMergeTree(
    '/clickhouse/tables/{shard}/events',
    '{replica}'
)
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_type, event_time);
```

Делаем ее реплицируемой при помощи использования движка ```ReplicatedMergeTree```

5. Убедимся, что таблица существует на всех 3-х репликах:

```bash
docker exec clickhouse1 clickhouse-client --query "SHOW TABLES"
docker exec clickhouse2 clickhouse-client --query "SHOW TABLES"
docker exec clickhouse3 clickhouse-client --query "SHOW TABLES"
---
events
events
events
```

## Часть 3 - Проверка репликации

1. Сгенерируем 100 000 строк:
```sql
INSERT INTO events
SELECT
    now() - INTERVAL number SECOND AS event_time,
    multiIf(
        number % 5 = 0, 'page_view',
        number % 5 = 1, 'click',
        number % 5 = 2, 'purchase',
        number % 5 = 3, 'login',
        'logout'
    ) AS event_type,
    number % 10000 AS user_id,
    concat('payload_', toString(number)) AS payload
FROM numbers(100000);
```
2. Вставим данные в первую реплику:
```bash
docker exec -i clickhouse1 clickhouse-client < sql/02_insert_data.sql
```

3. Проверим количество строк на трех узлах:
```bash
docker exec clickhouse1 clickhouse-client --query "SELECT count() FROM events"
docker exec clickhouse2 clickhouse-client --query "SELECT count() FROM events"
docker exec clickhouse3 clickhouse-client --query "SELECT count() FROM events"
---
100000
100000
100000
```
Все корректно скопировалось

4. Выводы с каждой реплики с ```system.replicas``` сохранены в ```/checks/replicas_status/node(1/2/3)```

Можем увидеть, что данные совпадают

## Часть 4 и 5 - Отказоустойчивость (Эксперименты) и ```system.replication_queue```

### Эксперимент A - потеря одной реплики

1. Остановим реплику 3:
```bash
docker stop clickhouse3
```

2. Вставим новые данные (100000 строк) в реплику 1:
```sql
INSERT INTO events
SELECT
    now() - INTERVAL number SECOND AS event_time,
    'experiment_a' AS event_type,
    number AS user_id,
    concat('experiment_a_payload_', toString(number)) AS payload
FROM numbers(100000)
```

3. Проверяем получила ли реплика 2 данные:
```sql
SELECT
    hostName() AS node,
    event_type,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
WHERE event_type = 'experiment_a'
GROUP BY node, event_type
FORMAT Vertical
```

4. Поднимаем реплику 3:
```bash
docker start clickhouse3
```

5. Сохраняем состояние очереди, пока реплика 3 синхронизируется:
```sql
SELECT *
FROM system.replication_queue
WHERE table = 'events'
FORMAT Vertical
```

6. Проверяем что реплика 3 догнала очередь:
```sql
SELECT
    hostName() AS node,
    event_type,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
WHERE event_type = 'experiment_a'
GROUP BY node, event_type
FORMAT Vertical
```

В эксперименте была проверена отказоустойчивость кластера при потере одной реплики.

До начала эксперимента на всех трёх репликах было одинаковое количество строк — 100000. Затем реплика 3 была остановлена, после чего в реплику 1 были вставлены новые 100000 строк с ```event_type = 'experiment_a'```.

После вставки данные сразу появились на двух активных репликах. Количество строк ```experiment_a``` на двух репликах составило 100000, а контрольная сумма ```sum_user_id``` совпала. Это подтверждает, что без одной реплики кластер продолжил принимать запись и реплицировать данные на оставшиеся доступные узлы.

После повторного запуска реплики 3 она автоматически синхронизировалась и получила недостающие данные. На реплике 3 также появилось 100000 строк с ```event_type = 'experiment_a'``` и такой же ```sum_user_id```.

Также во время синхонизации реплики 3 сохранили состояние очереди через ```system.replication_queue```. Вывод оказался пустым, а это значит что реплика уже успела обработать все задачи. Подробные логи можно посмотреть в ```/checks/replication_queue.txt```

Финальная проверка ```system.replicas``` показала, что все три реплики активны: ```active_replicas = 3```, ```total_replicas = 3```. Значения ```queue_size = 0```, ```inserts_in_queue = 0```, ```merges_in_queue = 0``` и ```absolute_delay = 0``` на всех узлах означают, что очередь репликации пуста, задержки нет, и все реплики полностью синхронизированы.

Итого, потеря одной реплики не привела к потере данных. После восстановления остановленная реплика успешно догнала остальные.

Логи можно посмотреть в ```/checks/experiment_a.txt```

### Эксперимент B — Потеря Keeper-узла

1. Останавливаем один узел Keeper:
```bash
docker stop keeper3
```

2. Проверяем что кворум жив:
```bash
echo mntr | nc localhost 9181 | grep zk_server_state || true
echo mntr | nc localhost 9182 | grep zk_server_state || true
echo mntr | nc localhost 9183 | grep zk_server_state || echo "keeper3 is unavailable"
```

3. Вставляем новые данные в реплику 1 пока один узел Keeper остановлен:
```sql
INSERT INTO events
SELECT
    now() - INTERVAL number SECOND AS event_time,
    'experiment_b_one_keeper_down' AS event_type,
    number AS user_id,
    concat('experiment_b_payload_', toString(number)) AS payload
FROM numbers(10000)
```

4. Проверяем вставились ли данные при остановленном одном Kepper:
```sql
SELECT
    hostName() AS node,
    event_type,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
WHERE event_type = 'experiment_b_one_keeper_down'
GROUP BY node, event_type
FORMAT Vertical
```

5. Останавливаем второй Keeper:
```bash
docker stop keeper2
```

6. Пытаемся вставить данные, когда кворума нет:
```sql
INSERT INTO events
SELECT
    now() AS event_time,
    'experiment_b_no_quorum' AS event_type,
    1 AS user_id,
    'no_quorum_payload' AS payload
```

7. Показываем что ```SELECT``` по прежнему работает локально:
```sql
SELECT
    hostName() AS node,
    count() AS rows
FROM events
FORMAT Vertical
```

8. Поднимаем все ранее остановленные узлы:
```bash
docker start keeper2
docker start keeper3
```

9. Проверяем состояние узлов после восстановления:
```bash
echo mntr | nc localhost 9181 | grep zk_server_state || true
echo mntr | nc localhost 9182 | grep zk_server_state || true
echo mntr | nc localhost 9183 | grep zk_server_state || true
```

В эксперименте была проверена устойчивость ClickHouse-кластера при потере узлов Keeper.

Был остановлен keeper3. После этого остались доступными ```keeper1``` и ```keeper2```.

Далее были вставленны 10000 строк с ```event_type = 'experiment_b_one_keeper_down'```. Вставка успешно выполнилась, а проверка показала, что на всех трёх репликах по 10000 строк и одинаковая ```sum_user_id = 49995000```. Значит, при потере одного Keeper-узла репликация продолжила работать и кворум сохранился.

Затем был остановлен второй Keeper-узел. После этого доступным остался только keeper1. Кворум был потерян. Попытка выполнить INSERT без кворума завершилась ошибкой. Исходя из этого, вывод - для записи в ```ReplicatedMergeTree``` требуется доступный кворум.

При этом ```SELECT``` продолжил работать локально: запрос на реплику 1 вернул 210000 строк (100000 изначально, после экперимена A стало 200000 строк, после эксперимента B добавилось еще 10000). В итоге, сохранённые данные остаются доступными для чтения даже при потере кворума, но новые операции записи в реплицируемую таблицу не могут быть согласованы.

Вывод: кластер выдерживает потерю одного Keeper-узла, но без кворума запись в ```ReplicatedMergeTree``` невозможна.

Логи можно посмотреть в ```/checks/experiment_b.txt```

### Эксперимент C — Конфликт данных

1. Останавливаем реплику 2:
```bash
docker stop clickhouse2
```

2. Вставляем данные в реплику 1:
```sql
INSERT INTO events
SELECT
    now() - INTERVAL number SECOND AS event_time,
    'experiment_c' AS event_type,
    number AS user_id,
    concat('experiment_c_payload_', toString(number)) AS payload
FROM numbers(10000)
```

3. Проверяем данные на работающих репликах:
```sql
SELECT
    hostName() AS node,
    event_type,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
WHERE event_type = 'experiment_c'
GROUP BY node, event_type
FORMAT Vertical
```

4. Поднимаем реплику 2:
```bash
docker start clickhouse2
```

5. Проверяем что реплика 2 получила те же данные:
```sql
SELECT
    hostName() AS node,
    event_type,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
WHERE event_type = 'experiment_c'
GROUP BY node, event_type
FORMAT Vertical
```

6. В завершении сравниваем все реплики:
```sql
SELECT
    hostName() AS node,
    count() AS rows,
    sum(user_id) AS sum_user_id
FROM events
FORMAT Vertical
```

Сначала была остановлена реплика 2. После этого через реплику 1 в таблицу ```events``` были записаны 10000 новых строк с ```event_type = 'experiment_c'```.

Проверка доступных реплик показала, что две работающие реплики содержат одинаковые данные: по 10000 строк ```experiment_c``` и одинаковую sum_user_id.

После повторного запуска реплики 2, она автоматически получила пропущенные данные. На ней также появилось 10000 строк experiment_c с тем же значением sum_user_id.

Проверка ```system.replicas``` на реплике 2 показала, что она находится в активна: ```is_readonly = 0```, ```active_replicas = 3```, ```total_replicas = 3```. Значения ```queue_size = 0```, ```inserts_in_queue = 0```, ```merges_in_queue = 0``` и ```absolute_delay = 0``` означают, что очередь полностью обработана и задержки нет.

В конце сравнение всех трёх реплик показало одинаковое общее количество строк — 220000 — и одинаковую сумму user_id. Это подтверждает, что после восстановления реплики 2 данные на всех репликах совпадают.

Таким образом, конфликт данных не возник. Остановленная реплика после запуска догнала остальные.

Логи можно посмотреть в ```/checks/experiment_c.txt```