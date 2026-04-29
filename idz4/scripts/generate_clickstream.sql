INSERT INTO events_distributed
SELECT
    toDate('2026-04-01') + toIntervalDay(number % 30) AS event_date,
    toDateTime('2026-04-01 00:00:00') + toIntervalSecond(number) AS event_time,
    toUInt64((number % 100000) + 1) AS user_id,
    concat('session_', toString(intDiv(number, 10))) AS session_id,
    arrayElement(
        ['page_view', 'click', 'add_to_cart', 'purchase', 'logout'],
        (number % 5) + 1
    ) AS event_type,
    concat('/page/', toString(number % 1000)) AS page_url,
    toUInt32(50 + (number % 300000)) AS duration_ms
FROM numbers(2000000);