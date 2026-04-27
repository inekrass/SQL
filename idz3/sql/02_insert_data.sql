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