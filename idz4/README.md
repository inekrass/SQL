# ИДЗ-4. Шардирование в ClickHouse

**Выполнил**: Некрасов Богдан<br>
**Группа**: Р4150<br>
**ClickHouse**: 24.8.14.39

## Часть 1 - Кластер 2x2

- Был развернут шардированный кластер ClickHouse ```cluster_2x2```

Кластер состоит из двух шардов, в каждом шарде по 2 реплики

| Шард | Реплика | Узел |
|---:|---:|---|
| 1 | 1 | `ch-s1-r1` |
| 1 | 2 | `ch-s1-r2` |
| 2 | 1 | `ch-s2-r1` |
| 2 | 2 | `ch-s2-r2` |

Описание кластера находится в ```config/clickhouse/cluster.xml```

- Макросы

Макрос ```{shard}``` одинаковый для реплик внутри одного шарда. Например, узлы ```ch-s1-r1``` и ```ch-s1-r2``` имеют значение 01, потому что оба относятся к первому шарду.

Макрос {replica} уникален для каждой реплики. Он нужен, чтобы ClickHouse мог отличать реплики друг от друга при создании таблиц на движке ```ReplicatedMergeTree```.

- Keeper

Также был развернут кворум из трех Keeper-узлов: keeper1, keeper2, keeper3

Внутренний порт 9181. Порты на хост 9181, 9182, 9183 соответственно.

- Проверка кластера через таблицу ```system.cluster```:

```sql
SELECT
   cluster,
   shard_num,
   replica_num,
   host_name,
   host_address,
   port
FROM system.clusters
WHERE cluster = 'cluster_2x2'
ORDER BY shard_num, replica_num
FORMAT PrettyCompact
```

Результат:
```bash
   ┌─cluster─────┬─shard_num─┬─replica_num─┬─host_name─┬─host_address─┬─port─┐
1. │ cluster_2x2 │         1 │           1 │ ch-s1-r1  │ 172.20.0.7   │ 9000 │
2. │ cluster_2x2 │         1 │           2 │ ch-s1-r2  │ 172.20.0.6   │ 9000 │
3. │ cluster_2x2 │         2 │           1 │ ch-s2-r1  │ 172.20.0.5   │ 9000 │
4. │ cluster_2x2 │         2 │           2 │ ch-s2-r2  │ 172.20.0.8   │ 9000 │
   └─────────────┴───────────┴─────────────┴───────────┴──────────────┴──────┘
```
Здесь видно, что кластер ```cluster_2x2``` описан корректно: в нём два шарда и две реплики в каждом шарде.

- Были проверены макросы на каждом узле через таблицу ```system.macros```

- Проверили здоровье и состояние кворума
```bash
echo ruok | nc localhost 9181
echo ruok | nc localhost 9182
echo ruok | nc localhost 9183

echo mntr | nc localhost 9181
echo mntr | nc localhost 9182
echo mntr | nc localhost 9183
```

Все контейнеры выдали ```imok```. А из результатов команды ```mntr``` видно что keeper3 получил роль ```leader```, а остальные ```follower```.

Результаты всех проверок в файле ```/checks/cluster_info.txt```

## Часть 2 - Локальные и распределённые таблицы (Предметная область — события пользовательской аналитики (clickstream))

Во второй части были созданы таблицы:

- локальная таблица `events_local` физически хранит данные на узлах ClickHouse. Движок - `ReplicatedMergeTree`

- распределённая таблица `events_distributed` - это таблица-посредник. Она сама строки не хранит, а только перенаправляет запросы к `events_local`. Движок - `Distributed`. Используется для работы со всем кластером как с одной таблицей:

   - при INSERT ClickHouse выбирает нужный шард по ключу шардирования
   - при SELECT ClickHouse обращается к локальным таблицам на узлах кластера и объединяет результат.

DDL можно найти в `/sql/01_create_local.sql` и `/sql/02_create_distributed.sql`

### Выбор ключа шардирования

В распределенной таблице мы использовали ключа шардирования `xxHash64(user_id)`, так как события в clickstream связаны с конкретным пользователем. И поэтому логичнее хранить все события пользователя в одном шарде.

Не взяли `event_date` так как данные за одну дату могли бы попадать в один шард. К примеру, если бы сегодня произошло много событий то один шард бы был перегружен, когда другие совободны.

Не взяли `rand()` так как это рандом и, например, события одного пользователя могли бы улететь в разные шарды.

### Проверка создания таблиц

- Команда `SHOW TABLES` нам показала что на каждом узле по 2 таблицы:
```bash
       ==ch-s1-r1==
   ┌─name───────────────┐
1. │ events_distributed │
2. │ events_local       │
   └────────────────────┘
       ==ch-s1-r2==
   ┌─name───────────────┐
1. │ events_distributed │
2. │ events_local       │
   └────────────────────┘
       ==ch-s2-r1==
   ┌─name───────────────┐
1. │ events_distributed │
2. │ events_local       │
   └────────────────────┘
       ==ch-s2-r2==
   ┌─name───────────────┐
1. │ events_distributed │
2. │ events_local       │
   └────────────────────┘
```

- Проверили какие движки на таблицах:
```sql
SELECT
   name,
   engine
FROM system.tables
WHERE database = 'default'
  AND name IN ('events_local', 'events_distributed')
ORDER BY name
FORMAT PrettyCompact
```
```bash
   ┌─name───────────────┬─engine──────────────┐
1. │ events_distributed │ Distributed         │
2. │ events_local       │ ReplicatedMergeTree │
   └────────────────────┴─────────────────────┘
```

- Проверяем работу макросов:
```sql
SELECT
    hostName() AS host,
    database,
    table,
    engine,
    is_leader,
    replica_name,
    zookeeper_path
FROM clusterAllReplicas('cluster_2x2', system.replicas)
WHERE table = 'events_local'
ORDER BY host
FORMAT PrettyCompact
```
```bash
   ┌─host─────┬─database─┬─table────────┬─engine──────────────┬─is_leader─┬─replica_name─┬─zookeeper_path─────────────────────┐
1. │ ch-s1-r1 │ default  │ events_local │ ReplicatedMergeTree │         1 │ s1r1         │ /clickhouse/tables/01/events_local │
   └──────────┴──────────┴──────────────┴─────────────────────┴───────────┴──────────────┴────────────────────────────────────┘
   ┌─host─────┬─database─┬─table────────┬─engine──────────────┬─is_leader─┬─replica_name─┬─zookeeper_path─────────────────────┐
2. │ ch-s1-r2 │ default  │ events_local │ ReplicatedMergeTree │         1 │ s1r2         │ /clickhouse/tables/01/events_local │
   └──────────┴──────────┴──────────────┴─────────────────────┴───────────┴──────────────┴────────────────────────────────────┘
   ┌─host─────┬─database─┬─table────────┬─engine──────────────┬─is_leader─┬─replica_name─┬─zookeeper_path─────────────────────┐
3. │ ch-s2-r1 │ default  │ events_local │ ReplicatedMergeTree │         1 │ s2r1         │ /clickhouse/tables/02/events_local │
   └──────────┴──────────┴──────────────┴─────────────────────┴───────────┴──────────────┴────────────────────────────────────┘
   ┌─host─────┬─database─┬─table────────┬─engine──────────────┬─is_leader─┬─replica_name─┬─zookeeper_path─────────────────────┐
4. │ ch-s2-r2 │ default  │ events_local │ ReplicatedMergeTree │         1 │ s2r2         │ /clickhouse/tables/02/events_local │
   └──────────┴──────────┴──────────────┴─────────────────────┴───────────┴──────────────┴────────────────────────────────────┘
```

Видим что макросы верно подставились в `{shard}` и `{replica}`

## Часть 3 - Наполнение и проверка распределения

1. Наполняем таблицу `events_distributed` тестовыми данными (2000000 строк) через скрипт `/scripts/generate_clickstream.sql`.

- Проверяем общее количество строк в `events_distributed`:
```sql
SELECT count()
FROM events_distributed
FORMAT PrettyCompac
```
```bash
   ┌─count()─┐
1. │ 2000000 │ -- 2.00 million
   └─────────┘
```
Запрос вернул значение `2 000 000`. Это означает, что в распределённой таблице доступно два миллиона записей, то есть вставка тестовых данных прошла успешно.

2. Проверяем распределение данных по шардам:

```sql
SELECT
   hostName() AS host,
   count() AS rows
FROM clusterAllReplicas('cluster_2x2', default.events_local)
GROUP BY host
ORDER BY host
FORMAT PrettyCompact
```
```bash
   ┌─host─────┬────rows─┐
1. │ ch-s1-r1 │ 1002360 │
2. │ ch-s1-r2 │ 1002360 │
3. │ ch-s2-r1 │  997640 │
4. │ ch-s2-r2 │  997640 │
   └──────────┴─────────┘
```

3. Проверяем что ни один `user_id` не попал в разные шарды:

```sql
SELECT
   user_id,
   uniq(hostName()) AS hosts_count,
   groupUniqArray(hostName()) AS hosts,
   count() AS rows
FROM clusterAllReplicas('cluster_2x2', default.events_local)
GROUP BY user_id
ORDER BY user_id
LIMIT 10
FORMAT PrettyCompact
```
```bash
    ┌─user_id─┬─hosts_count─┬─hosts───────────────────┬─rows─┐
 1. │       1 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 2. │       2 │           2 │ ['ch-s1-r2','ch-s1-r1'] │   40 │
 3. │       3 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 4. │       4 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 5. │       5 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 6. │       6 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 7. │       7 │           2 │ ['ch-s2-r2','ch-s2-r1'] │   40 │
 8. │       8 │           2 │ ['ch-s1-r2','ch-s1-r1'] │   40 │
 9. │       9 │           2 │ ['ch-s1-r2','ch-s1-r1'] │   40 │
10. │      10 │           2 │ ['ch-s1-r2','ch-s1-r1'] │   40 │
    └─────────┴─────────────┴─────────────────────────┴──────┘
```
Так как мы задали ключ шардирования `xxHash64(user_id)`, события одного пользователя лежат в одном и том же шарде

Результаты всех проверок лежат в `/checks/data_distribution.txt`

## Часть 4 - Запросы через Distributed

### Глобальный COUNT

- Сначала выполнили проверку общего количества записей через `events_distributed`
```sql
SELECT
   count() AS distributed_rows
FROM events_distributed;
```
```bash
   ┌─distributed_rows─┐
1. │          2000000 │ -- 2.00 million
   └──────────────────┘
```
Через эту таблицу доступны все два миллиона строк.

- Далее была выполнена проверка суммы локальных данных по шардам:
```sql
SELECT
   sum(rows) AS local_rows_sum
FROM
(
   SELECT
      hostName() AS host,
      count() AS rows
   FROM cluster('cluster_2x2', default.events_local)
   GROUP BY host
);
```
```bash
   ┌─local_rows_sum─┐
1. │        2000000 │ -- 2.00 million
   └────────────────┘
```
Вывод совпал, а это значит что распределенная таблица корректно считывает данные с кластера.

### GROUP BY с шардированным ключом

Выполняем группировку по ключу шардирования (`user_id`):
```sql
SELECT
   user_id,
   count() AS events_count
FROM events_distributed
GROUP BY user_id
ORDER BY events_count DESC, user_id
LIMIT 10
FORMAT PrettyCompact;
```
```bash
    ┌─user_id─┬─events_count─┐
 1. │       1 │           20 │
 2. │       2 │           20 │
 3. │       3 │           20 │
 4. │       4 │           20 │
 5. │       5 │           20 │
 6. │       6 │           20 │
 7. │       7 │           20 │
 8. │       8 │           20 │
 9. │       9 │           20 │
10. │      10 │           20 │
    └─────────┴──────────────┘
```
Видим что у каждого пользователя по 20 событий. Все события пользователя попадают в один и тот же шард, так как мы делали группировку по ключу шардирования. Ранее мы делали проверку, что все события пользователя попадают в один и тот же шард.

Это эффективно, так как ClickHouse не придется собирать данные для одного пользователя по разным шардам.

### GROUP BY без шардированного ключа

Выполняем группировку по полю `page_url`. То есть не по ключу шардирования:
```sql
SELECT
   page_url,
   count() AS visits
FROM events_distributed
GROUP BY page_url
ORDER BY visits DESC, page_url
LIMIT 10
FORMAT PrettyCompact;
```
```bash
    ┌─page_url──┬─visits─┐
 1. │ /page/0   │   2000 │
 2. │ /page/1   │   2000 │
 3. │ /page/10  │   2000 │
 4. │ /page/100 │   2000 │
 5. │ /page/101 │   2000 │
 6. │ /page/102 │   2000 │
 7. │ /page/103 │   2000 │
 8. │ /page/104 │   2000 │
 9. │ /page/105 │   2000 │
10. │ /page/106 │   2000 │
    └───────────┴────────┘
```
Так как `page_url` не ключ шардирования, события одной страниц могут находиться на разных шардах. Поэтому ClickHouse сначала считывает промежуточные результаты на шардах и потом объединяет их.

### JOIN со справочной таблицей `user_dict`:

Сначала создадим справочную таблицу `user_dict` с полями `user_id, name, segment` на движке `ReplicatedMergeTree`, и заполним ее 100000 строками где segment имеет значения `new, regular, vip, inactive`:
```sql
CREATE TABLE IF NOT EXISTS user_dict ON CLUSTER cluster_2x2
(
   user_id UInt64,
   name String,
   segment LowCardinality(String)
)
ENGINE = ReplicatedMergeTree(
   '/clickhouse/tables/user_dict',
   '{replica}'
)
ORDER BY user_id;
```

Выполним обычный JOIN:
```sql
SELECT
   d.segment,
   count() AS events_count
FROM events_distributed AS e
ANY INNER JOIN user_dict AS d
   ON e.user_id = d.user_id
GROUP BY d.segment
ORDER BY events_count DESC;
```
```bash
segment  | events_count
new      | 25000
regular  | 25000
inactive | 25000
vip      | 25000
```

Также вариант с `GLOBAL JOIN`:
```sql
SELECT
   d.segment,
   count() AS events_count
FROM events_distributed AS e
GLOBAL ANY INNER JOIN user_dict AS d
   ON e.user_id = d.user_id
GROUP BY d.segment
ORDER BY events_count DESC;
```
```bash
   ┌─segment──┬─events_count─┐
1. │ new      │        25000 │
2. │ regular  │        25000 │
3. │ inactive │        25000 │
4. │ vip      │        25000 │
   └──────────┴──────────────┘
```


- Проблема broadcast JOIN:

Каждый шард может видеть только свою локальную часть справочника, из-за этого ClickHouse может выполнить соединение локально на каждом шарде и получить неполный результат.

Этого можно избежать использовав `GLOBAL JOIN`:
При нем ClickHouse сначала рассылает справочник на все шарды, и после этого каждый шард выполняет соединение всех событий с полной копией справочника.

Результаты запросов в `checks/distributed_queries.txt` 