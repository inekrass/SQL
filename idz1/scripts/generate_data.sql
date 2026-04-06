INSERT INTO orders_raw (
    order_id,
    order_date,
    customer_name,
    customer_email,
    customer_phone,
    delivery_address,
    product_names,
    product_prices,
    product_quantities,
    total_amount,
    status
)
SELECT
    gs AS order_id,
    DATE '2024-01-01' + (gs % 365),
    'Клиент ' || gs,
    'client' || gs || '@mail.ru',
    '+7999' || LPAD(gs::text, 7, '0'),
    'Город, улица ' || gs,
    CASE
        WHEN gs % 3 = 0 THEN 'Ноутбук, Мышь, Коврик'
        WHEN gs % 3 = 1 THEN 'Монитор, Кабель HDMI'
        ELSE 'Клавиатура, Мышь'
    END,
    CASE
        WHEN gs % 3 = 0 THEN '85000, 1500, 500'
        WHEN gs % 3 = 1 THEN '22000, 900'
        ELSE '3500, 1200'
    END,
    CASE
        WHEN gs % 3 = 0 THEN '1, 1, 2'
        WHEN gs % 3 = 1 THEN '1, 2'
        ELSE '1, 1'
    END,
    CASE
        WHEN gs % 3 = 0 THEN 87500
        WHEN gs % 3 = 1 THEN 23800
        ELSE 4700
    END,
    CASE
        WHEN gs % 4 = 0 THEN 'new'
        WHEN gs % 4 = 1 THEN 'processing'
        WHEN gs % 4 = 2 THEN 'shipped'
        ELSE 'delivered'
    END
FROM generate_series(1, 1000) AS gs;