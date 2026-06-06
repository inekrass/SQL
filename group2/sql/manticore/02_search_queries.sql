-- Полнотекстовый поиск по текстам отзывов.
SELECT id, product_id, customer_id, rating, title
FROM reviews
WHERE MATCH('otlichnyy tovar rekomenduyu')
LIMIT 10;

-- Поиск с фильтрами по рейтингу и товару.
SELECT id, product_id, customer_id, rating, title
FROM reviews
WHERE rating >= 4 AND product_id = 42
LIMIT 10;

-- Фасетный поиск: Manticore отдельно возвращает распределение отзывов по рейтингу.
SELECT id, rating
FROM reviews
LIMIT 1
FACET rating ORDER BY count(*) DESC;

-- Поиск негативных отзывов по словам про брак, поломку и возврат.
SELECT id, product_id, customer_id, rating, title
FROM reviews
WHERE MATCH('brak slomalsya vozvrat')
LIMIT 10;
