DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    delivery_address TEXT NOT NULL,
    UNIQUE (customer_name, customer_email, customer_phone, delivery_address)
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_price NUMERIC NOT NULL,
    UNIQUE (product_name, product_price)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    total_amount NUMERIC NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    product_quantity INTEGER NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO customers (
    customer_name,
    customer_email,
    customer_phone,
    delivery_address
)
SELECT DISTINCT
    customer_name,
    customer_email,
    customer_phone,
    delivery_address
FROM orders_1nf;

INSERT INTO products (
    product_name,
    product_price
)
SELECT DISTINCT
    product_name,
    product_price
FROM order_items_1nf;

INSERT INTO orders (
    order_id,
    order_date,
    customer_id,
    total_amount,
    status
)
SELECT
    o.order_id,
    o.order_date,
    c.customer_id,
    o.total_amount,
    o.status
FROM orders_1nf o
JOIN customers c
  ON c.customer_name = o.customer_name
 AND c.customer_email = o.customer_email
 AND c.customer_phone = o.customer_phone
 AND c.delivery_address = o.delivery_address;

INSERT INTO order_items (
    order_id,
    product_id,
    product_quantity
)
SELECT
    oi.order_id,
    p.product_id,
    oi.product_quantity
FROM order_items_1nf oi
JOIN products p
  ON p.product_name = oi.product_name
 AND p.product_price = oi.product_price;