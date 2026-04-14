CREATE EXTENSION IF NOT EXISTS pg_trgm;
DROP INDEX IF EXISTS idx_customers_3nf_email;
DROP INDEX IF EXISTS idx_customers_3nf_name_btree;
DROP INDEX IF EXISTS idx_customers_3nf_name_trgm;
-- 1. Поиск клиента по email
-- До индекса

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_email = 'client1@mail.ru';

-- 2. Создание B-tree индекса по email

DROP INDEX IF EXISTS idx_customers_3nf_email;

CREATE INDEX idx_customers_3nf_email
ON customers_3nf(customer_email);

-- 3. Поиск клиента по email
-- После индекса

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_email = 'client1@mail.ru';

-- 4. Поиск клиента по подстроке имени
-- Без trigram-индекса
-- Здесь обычный B-tree индекс не помогает

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';

-- 5. Демонстрация, что обычный B-tree по имени
-- не помогает для ILIKE '%...%'

DROP INDEX IF EXISTS idx_customers_3nf_name_btree;

CREATE INDEX idx_customers_3nf_name_btree
ON customers_3nf(customer_name);

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';

-- 6. Создание GIN-индекса с pg_trgm для поиска по имени

DROP INDEX IF EXISTS idx_customers_3nf_name_trgm;

CREATE INDEX idx_customers_3nf_name_trgm
ON customers_3nf
USING GIN (customer_name gin_trgm_ops);

-- 7. Поиск клиента по подстроке имени
-- После GIN + pg_trgm

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';

-- 8. Отключаем Seq Scan для демонстрации использования pg_trgm
SET enable_seqscan = OFF;

EXPLAIN ANALYZE
SELECT
    customer_id,
    customer_name,
    customer_email,
    customer_phone
FROM customers_3nf
WHERE customer_name ILIKE '%Клиент 1%';

SET enable_seqscan = ON;