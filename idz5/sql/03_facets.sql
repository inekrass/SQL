-- 5.1 Агрегирование по категориям
SELECT category, COUNT(*) AS cnt, AVG(price) AS avg_price
FROM products
WHERE MATCH('gaming')
GROUP BY category
ORDER BY cnt DESC;

-- 5.2 Facet поиск по категориям 
SELECT id, title, price
FROM products
WHERE MATCH('gaming')
FACET category ORDER BY COUNT(*) DESC
FACET brand ORDER BY COUNT(*) DESC;