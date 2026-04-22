# ИДЗ-2. ClickHouse: колоночное хранилище, движки и OLAP-аналитика

**Выполнил**: Некрасов Богдан<br>
**Группа**: Р4150<br>
**ClickHouse**: 24.8.14.39

## Часть 1 - Установка и начальная настройка.
1. Настраиваем контейнер ClickHouse в ```docker-compose.yml```
```yml
services:
  clickhouse-server:
    image: clickhouse/clickhouse-server:24.8
    container_name: idz2_nekrasov
    environment:
      CLICKHOUSE_SKIP_USER_SETUP: "1"
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
    volumes:
      - ./config/config.d:/etc/clickhouse-server/config.d:ro
      - ./config/users.d:/etc/clickhouse-server/users.d:ro
      - ./sql:/sql:ro
      - ./scripts:/scripts
      - clickhouse_data:/var/lib/clickhouse
      - clickhouse_logs:/var/log/clickhouse-server
    ports:
      - "8123:8123"
      - "9000:9000"
    restart: unless-stopped

volumes:
  clickhouse_data:
  clickhouse_logs:
```

2. Настраиваем ```config/config.d/listen.xml``` для прослушивания на ```0.0.0.0```:

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
</clickhouse>
```

3. Настраиваем ```config/users.d/users.xml```, в котором создаем профиль readonly и двух пользователей: ```default``` и ```analyst``` с профилем readonly:
```xml
<?xml version="1.0"?>
<clickhouse>
    <profiles>
        <readonly>
            <readonly>1</readonly>
        </readonly>
    </profiles>

    <users>
        <default>
            <networks>
                <ip>::/0</ip>
                <ip>0.0.0.0/0</ip>
            </networks>
        </default>

        <analyst>
            <password>123</password>
            <profile>readonly</profile>
            <quota>default</quota>
            <networks>
                <ip>::/0</ip>
                <ip>0.0.0.0/0</ip>
            </networks>
        </analyst>
    </users>
</clickhouse>
```

4. Проверяем подлкючение от обоих пользователей:

```
docker exec -it idz2_nekrasov clickhouse-client -u default --query "SELECT currentUser(), version()"
---
default 24.8.14.39
```

```
docker exec -it idz2_nekrasov clickhouse-client -u analyst --password 123 --query "SELECT currentUser(), version()"
---
analyst 24.8.14.39
```

5. Проверка, что пользователь ```analyst``` не имеет прав на запись:
```
docker exec -it idz2_nekrasov clickhouse-client -u analyst --password 123 --query "CREATE DATABASE test_db"
---
Received exception from server (version 24.8.14):
Code: 164. DB::Exception: Received from localhost:9000. DB::Exception: analyst: Cannot execute query in readonly mode. (READONLY)
```

## Часть 2. Проектирование схемы — плоская денормализованная таблица.

В ClickHouse используются денормализованные таблицы потому что это OLAP-СУБД для аналитики, а не OLTP, как PostgreSQL:
- Запросы к одной широкой таблице обычно выполнять проще и быстрее, чем делать много JOIN.
- ClickHouse хорошо подходит для чтения, агрегаций и отчётов по большим данным.
- Схема становится удобнее для аналитики, когда все нужные поля уже лежат в одной таблице.

### Ответы на вопросы:

- ***Почему нет JOIN-ов на лету:*** В ClickHouse чаще выгоднее хранить данные сразу в одной широкой таблице, чем каждый раз соединять несколько таблиц в запросе. JOIN на больших объёмах данных может замедлять аналитику, поэтому для отчётов удобнее сразу иметь готовую денормализованную таблицу.

- ***Почему избыточность данных компенсируется сжатием:*** В таблице данные дублируются, но ClickHouse хранит их по колонкам и хорошо сжимает повторяющиеся значения (через словарное кодирование или алгоритмы оптимизации числовых последовательностей). Поэтому лишние данные занимают не так много места.

- ***Почему ```LowCardinality``` заменяет справочные таблицы.*** Если в колонке мало уникальных значений, например статус заказа, категория или регион, ClickHouse хранит такие значения через внутренний словарь и ссылки на него, что уменьшает объём хранения и ускоряет обработку. Поэтому можно хранить их прямо в основной таблице в виде ```LowCardinality```.

### Создание базы данных и таблиц
#### Создание БД
```
docker exec -i idz2_nekrasov clickhouse-client -u default < sql/01_create_db.sql
```

#### Создание таблицы ```orders_flat```
```
docker exec -i idz2_nekrasov clickhouse-client -u default < sql/02_orders_flat.sql
```
```sql
--Таблица orders_flat
CREATE TABLE idz2.orders_flat
(
    order_date       Date,
    order_datetime   DateTime,
    order_id         UInt64,
    customer_id      UInt64,
    customer_name    String,
    customer_email   LowCardinality(String),
    region           LowCardinality(String),
    product_id       UInt64,
    product_name     String,
    category         LowCardinality(String),
    quantity         UInt32,
    price            Decimal(12, 2),
    line_total       Decimal(12, 2),
    order_status     LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(order_date)
ORDER BY (category, toStartOfHour(order_datetime), order_status, order_id);
```
#### Создание таблицы ```orders_ttl```
```
docker exec -i idz2_nekrasov clickhouse-client -u default < sql/03_orders_ttl.sql
```
```sql
--Таблица orders_ttl
CREATE TABLE idz2.orders_ttl
(
    order_date       Date,
    order_datetime   DateTime,
    order_id         UInt64,
    customer_id      UInt64,
    customer_name    String,
    customer_email   LowCardinality(String),
    region           LowCardinality(String),
    product_id       UInt64,
    product_name     String,
    category         LowCardinality(String),
    quantity         UInt32,
    price            Decimal(12, 2),
    line_total       Decimal(12, 2),
    order_status     LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(order_date)
ORDER BY (category, toStartOfHour(order_datetime), order_status, order_id)
TTL order_date + INTERVAL 90 DAY DELETE;
```

#### Создание таблицы ```monthly_sales```
```
docker exec -i idz2_nekrasov clickhouse-client -u default < sql/04_monthly_sales.sql
```
```sql
CREATE TABLE idz2.monthly_sales
(
    month          Date,
    category       LowCardinality(String),
    region         LowCardinality(String),
    total_quantity UInt64,
    total_revenue  Decimal(14, 2)
)
ENGINE = SummingMergeTree()
ORDER BY (month, category, region);
```

### Обоснование ```ORDER BY```

#### ```ORDER BY``` в ```orders_flat``` и ```orders_ttl```

В этих таблицах используется 
```sql
ORDER BY (category, toStartOfHour(order_datetime), order_status, order_id)
```

- ```category``` - Необходим для того чтобы товары одной категории лежали рядом.
- ```toStartOfHour(order_datetime)``` - Для эффективной работы с временными интервалами и агрегацией по периодам.
- ```order_status``` - Для фильтрации по состоянию заказов.


Так порядок хранения соответствует типичным аналитическим сценариям: отчеты по категориям товаров, статусам заказов и временным периодам.

#### ```ORDER BY``` в ```monthly_sales```

В этой таблице используется 
```sql
ORDER BY (month, category, region)
```

Такой порядок логичен для аналитики продаж, так как позволяет быстро получать данные по месяцам, категориям и регионам.

## Часть 3. Загрузка данных.

Для загрузки данных в ClickHouse был выбран  Python-скрипт ```scripts/pg_to_ch.py```, который делает JOIN нормализованных таблиц ```orders_3nf```, ```order_items_3nf```, ```products_3nf```, ```categories```, ```customers_3nf``` и ```addresses``` PostgreSQL из ИДЗ-1 и записывает результат в таблицы ```idz2.orders_flat``` и ```idz2.orders_ttl``` ClickHouse.

***ШАГИ:***
1. Запустить контейнеры PostgreSQL из ИДЗ-1 и ClickHouse из ИДЗ-2.
2. Установить Python-зависимости:
```bash
python3 -m pip install psycopg2-binary clickhouse-connect
```
3. Запустить скрипт загрузки: 
```bash
python3 scripts/pg_to_ch.py
```

После запуска скрипта из PostgreSQL было считано 2335 строк:
```
Reading data from PostgreSQL...
Fetched 2335 rows from PostgreSQL
```

Они были успешно загружены в таблицы ```idz2.orders_flat``` и ```idz2.orders_ttl```:
```
Loading data into ClickHouse...
Inserted 2335 rows into idz2.orders_flat
Inserted 2335 rows into idz2.orders_ttl
Done.
```

Проверим заполненные таблицы:
```
docker exec -it idz2_nekrasov clickhouse-client -u default --query "SELECT count() FROM idz2.orders_flat"
---
2335
```
В таблицу ```idz2.orders_flat``` было загружено 2335 строк

```
docker exec -it idz2_nekrasov clickhouse-client -u default --query "SELECT count() FROM idz2.orders_ttl"
---
2
```
Столько же было загружено в таблицу ```idz2.orders_ttl```, но после проверки в ней осталось только 2 строки.
В таблице ```idz2.orders_ttl``` задано правило:
```sql
TTL order_date + INTERVAL 90 DAY DELETE
```
Данные из ИДЗ 1 старше 90 дней, поэтому ClickHouse их удалил.

## Часть 4. Те же бизнес-запросы, другой движок.

Предварительно заполняем таблицу ```monthly_sales```
```sql
INSERT INTO monthly_sales
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    region,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category,
    region;
```

Выполняем аналогичные запросы из ИДЗ-1, но на ClickHouse:

1. ***Топ-10 товаров по выручке:***
```sql
SELECT
    product_id,
    product_name,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    product_id,
    product_name
ORDER BY total_revenue DESC
LIMIT 10;
```
Запрос выполнился за 0.013 сек.
Результат в ```checks/top10_products.txt```

2. ***Ежемесячная динамика продаж по категориям:***
```sql
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category
ORDER BY
    month,
    category;
```
Запрос выполнился за 0.010 сек.
Результат в ```checks/monthly_sales.txt```

3. ***Процентиль p95/p99 стоимости заказа:***
```sql
SELECT
    quantileExact(0.95)(order_total) AS p95_order_value,
    quantileExact(0.99)(order_total) AS p99_order_value
FROM
(
    SELECT
        order_id,
        sum(line_total) AS order_total
    FROM orders_flat
    GROUP BY order_id
);
```
Мы сначала считаем сумму заказа, потом берём процентиль.

Результат:
```
   ┌─p95_order_value─┬─p99_order_value─┐
1. │           87500 │           87500 │
   └─────────────────┴─────────────────┘
0.009
```
Процентиль показывает, какое значение является верхней границей для определённой доли данных.

В данном случае p95 и p99 стоимости заказа оказались равны 87500. Это означает, что 95% заказов имеют стоимость не больше 87500, 99% заказов тоже имеют стоимость не больше 87500.

Запрос выполнился за 0.009 сек.

4. ***Поиск клиента по подстроке email:***
```sql
SELECT
    customer_id,
    customer_name,
    customer_email
FROM orders_flat
WHERE positionCaseInsensitive(customer_email, 'mail') > 0
GROUP BY
    customer_id,
    customer_name,
    customer_email
ORDER BY customer_id
LIMIT 20;
```
В PostgreSQL мы делали поиск через ```LIKE/ILIKE```, а в ClickHouse удобнее использовать поиск через ```positionCaseInsensitive(customer_email, 'mail')```. Так ищется подстрока внутри строки без учёта регистра.

Результат в ```checks/email_search.txt```

Запрос выполнился за 0.010 сек.

5. ***Сравнение результата из ```orders_flat``` и ```monthly_sales``` (SummingMergeTree):***
```sql
-- Агрегат напрямую из orders_flat
SELECT
    toStartOfMonth(order_date) AS month,
    category,
    region,
    sum(quantity) AS total_quantity,
    sum(line_total) AS total_revenue
FROM orders_flat
GROUP BY
    month,
    category,
    region
ORDER BY
    month,
    category,
    region;

-- Тот же результат из monthly_sales
SELECT
    month,
    category,
    region,
    sum(total_quantity) AS total_quantity,
    sum(total_revenue) AS total_revenue
FROM monthly_sales
GROUP BY
    month,
    category,
    region
ORDER BY
    month,
    category,
    region;
```
Результат в ```checks/summing_vs_raw.txt```

Первый запрос выполнился за 0.012 сек, а второй за 0.006 сек.

Запрос к ```monthly_sales``` выполнился примерно в два раза быстрее, чем аналогичный запрос к ```orders_flat```. Так как в ```orders_flat``` агрегаты считаются во время выполнения запроса, а в ```monthly_sales``` эти агрегаты уже предвычислены и сохранены заранее.

```SummingMergeTree``` в данном случае действительно помогает ускорить аналитику, если один и тот же агрегированный результат нужен часто.

## Часть 5. Демонстрация TTL

В таблице ```idz2.orders_ttl``` сейчас 2 строки:
```bash
Row 1:
──────
order_date:     2026-04-12
order_datetime: 2026-04-11 21:00:00
order_id:       1001
customer_id:    1
customer_name:  Клиент 91
customer_email: client91@mail.ru
region:         Город, улица 91
product_id:     1
product_name:   Мышь
category:       Периферия
quantity:       1
price:          1500
line_total:     1500
order_status:   new

Row 2:
──────
order_date:     2026-04-12
order_datetime: 2026-04-11 21:00:00
order_id:       1002
customer_id:    1
customer_name:  Клиент 91
customer_email: client91@mail.ru
region:         Город, улица 91
product_id:     1
product_name:   Мышь
category:       Периферия
quantity:       1
price:          1500
line_total:     1500
order_status:   new
```

Смотрим ```system.parts``` **до** TTL:
```bash
Row 1:
──────
database:  idz2
table:     orders_ttl 
partition: 202604 #Строки сейчас лежат в партиции апреля 2026
name:      202604_13_13_1 #имя части данных
active:    1 #эта часть активная, то есть реально используется таблицей
rows:      2 #в этой части сейчас 2 строки
```

Вставим 1000 строк со старой датой, чтобы проверить как работает TTL. (скрипт ```scripts/generate_ttl_data.sql```)

Смотрим ```system.parts``` ***после*** вставки
```bash
Row 1:
──────
database:  idz2
table:     orders_ttl
partition: 202401
name:      202401_15_15_0
active:    1
rows:      1000

Row 2:
──────
database:  idz2
table:     orders_ttl
partition: 202604
name:      202604_13_13_1
active:    1
rows:      2
```
Появился новый part, который лежит в партиции 202401. В этом part 1000 строк

Выполним слияние этих частей командой:
```sql
OPTIMIZE TABLE idz2.orders_ttl FINAL;
```

Смотрим ```system.parts``` ***после*** слияния:
```bash
Row 1:
──────
database:  idz2
table:     orders_ttl
partition: 202401
name:      202401_15_15_0
active:    0
rows:      1000

Row 2:
──────
database:  idz2
table:     orders_ttl
partition: 202401
name:      202401_15_15_1
active:    1
rows:      0

Row 3:
──────
database:  idz2
table:     orders_ttl
partition: 202604
name:      202604_13_13_1
active:    0
rows:      2

Row 4:
──────
database:  idz2
table:     orders_ttl
partition: 202604
name:      202604_13_13_2
active:    1
rows:      2
```
- Для партиции 202401 старая часть с 1000 строками стала неактивной, а новая активная часть содержит 0 строк — это значит, что TTL удалил старые данные;
- Для партиции 202604 часть тоже была пересобрана, но 2 строки сохранились, потому что они не просрочены.

## Часть 6. Системные таблицы и сжатие

При проверке таблицы orders_flat через system.parts выяснилось, что все её части имеют тип Compact. ```orders_flat     Compact 13```

Поэтому запрос к ```system.parts_columns``` не показал полезной поколоночной статистики сжатия: для всех колонок были получены значения 0.00 B.
Это связано с тем, что на текущем объёме данных ClickHouse хранит таблицу в формате compact parts.

Сейчас в таблице ```orders_flat``` 2335 строк.

Дополним таблицу до 1 000 000 строк (скрипт ```scripts/generate_million_raws.sql```)

Теперь в таблице 1 000 000 строк:
```
docker exec -it idz2_nekrasov clickhouse-client -u default --query "                         
SELECT count()
FROM idz2.orders_flat
"
---
1000000
```
При проверке таблицы ```orders_flat```, в которой 1 000 000 строк, через system.parts выяснилось, что все её части по прежнему имеют тип Compact. ```orders_flat     Compact 37``` и вывод получается следующим:

```
category        0.00 B  0.00 B  nan
quantity        0.00 B  0.00 B  nan
order_id        0.00 B  0.00 B  nan
region  0.00 B  0.00 B  nan
price   0.00 B  0.00 B  nan
customer_id     0.00 B  0.00 B  nan
product_id      0.00 B  0.00 B  nan
order_datetime  0.00 B  0.00 B  nan
customer_name   0.00 B  0.00 B  nan
line_total      0.00 B  0.00 B  nan
order_status    0.00 B  0.00 B  nan
product_name    0.00 B  0.00 B  nan
customer_email  0.00 B  0.00 B  nan
order_date      0.00 B  0.00 B  nan
```

## Часть 7. Сравнение с PostgreSQL

| Запрос / Операция | PostgreSQL (3NF) | ClickHouse (flat) | Вывод |
|-------------------|------------------|--------------------|-------|
| Вставка 1 строки  | 19.080 мс | 0.011 мс | PostgreSQL лучше подходит для OLTP-вставок. ClickHouse тоже может вставить одну строку быстро, но он рассчитан в первую очередь на пакетные вставки. |
| Топ-10 товаров (1M строк) | 169.691 мс | 0.044 мс | ClickHouse лучше подходит для аналитических запросов на больших объёмах данных. На плоской таблице и колоночном хранении агрегатный запрос выполняется намного быстрее, чем в PostgreSQL. |
| JOIN 4 таблиц | 0.122 мс | не нужен | В PostgreSQL JOIN работает быстро, но он всё равно нужен для получения итоговых данных. В ClickHouse такой JOIN вообще не нужен, потому что данные заранее денормализованы и уже лежат в одной таблице. |
| Обновление статуса | 1.002 мс | 0.007 (Через ALTER TABLE) | PostgreSQL лучше подходит для частых обновлений данных. В ClickHouse обновление возможно, но делается через ALTER TABLE ... UPDATE. |
| Размер на диске (1M строк) | 163 MB (Общий размер) | 24.44 MB (```order_flat```) | ClickHouse хранит 1 млн строк компактнее за счёт колоночного формата и сжатия. |
| Поиск по подстроке | 2.409 мс | 0.169 мс | PostgreSQL тоже умеет хорошо решать такую задачу, особенно если использовать специальные индексы. Для такого поиска можно использовать обе СУБД, но это не главное преимущество ClickHouse. |

Результаты запросов в ```checks/pg_vs_ch_comparison.txt```