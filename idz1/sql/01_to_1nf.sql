DROP TABLE IF EXISTS order_items_1nf;
DROP TABLE IF EXISTS orders_1nf;

CREATE TABLE orders_1nf (
    order_id INTEGER PRIMARY KEY,
    order_date DATE,
    customer_name TEXT,
    customer_email TEXT,
    customer_phone TEXT,
    delivery_address TEXT,
    total_amount NUMERIC,
    status TEXT
);

CREATE TABLE order_items_1nf (
    order_id INTEGER,
    product_name TEXT,
    product_price NUMERIC,
    product_quantity INTEGER,
    FOREIGN KEY (order_id) REFERENCES orders_1nf(order_id)
);

INSERT INTO orders_1nf (
    order_id,
    order_date,
    customer_name,
    customer_email,
    customer_phone,
    delivery_address,
    total_amount,
    status
)
SELECT DISTINCT
    order_id,
    order_date,
    customer_name,
    customer_email,
    customer_phone,
    delivery_address,
    total_amount,
    status
FROM orders_raw;

INSERT INTO order_items_1nf (
    order_id,
    product_name,
    product_price,
    product_quantity
)
SELECT
    r.order_id,
    trim(names.product_name) AS product_name,
    trim(prices.product_price)::numeric AS product_price,
    trim(qtys.product_quantity)::integer AS product_quantity
FROM orders_raw r
CROSS JOIN LATERAL unnest(string_to_array(r.product_names, ',')) WITH ORDINALITY AS names(product_name, pos)
JOIN LATERAL unnest(string_to_array(r.product_prices, ',')) WITH ORDINALITY AS prices(product_price, pos2)
    ON pos = pos2
JOIN LATERAL unnest(string_to_array(r.product_quantities, ',')) WITH ORDINALITY AS qtys(product_quantity, pos3)
    ON pos = pos3;