-- 1. Глобальный COUNT
SELECT
    count() AS distributed_rows
FROM events_distributed
FORMAT PrettyCompact;

-- 1.2. COUNT на каждом узле
SELECT
    sum(rows) AS local_rows_sum
FROM
(
    SELECT
        hostName() AS host,
        count() AS rows
    FROM cluster('cluster_2x2', default.events_local)
    GROUP BY host
)
FORMAT PrettyCompact;

-- 2. GROUP BY с шардированным ключом — top-10 пользователей по числу событий.
SELECT
    user_id,
    count() AS events_count
FROM events_distributed
GROUP BY user_id
ORDER BY events_count DESC, user_id
LIMIT 10
FORMAT PrettyCompact;

-- 3. GROUP BY без шардированного ключа — top-10 страниц по числу визитов.
SELECT
    page_url,
    count() AS visits
FROM events_distributed
GROUP BY page_url
ORDER BY visits DESC, page_url
LIMIT 10
FORMAT PrettyCompact;

-- 4. JOIN через Distributed.
SELECT
    d.segment,
    count() AS events_count
FROM events_distributed AS e
ANY INNER JOIN user_dict AS d
    ON e.user_id = d.user_id
GROUP BY d.segment
ORDER BY events_count DESC
FORMAT PrettyCompact;

-- 4. JOIN через Distributed. Используем GLOBAL ANY JOIN для оптимизации.
SELECT
    d.segment,
    count() AS events_count
FROM events_distributed AS e
GLOBAL ANY INNER JOIN user_dict AS d
    ON e.user_id = d.user_id
GROUP BY d.segment
ORDER BY events_count DESC
FORMAT PrettyCompact;