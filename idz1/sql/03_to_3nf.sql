DROP TABLE IF EXISTS order_items_3nf CASCADE;
DROP TABLE IF EXISTS orders_3nf CASCADE;
DROP TABLE IF EXISTS products_3nf CASCADE;
DROP TABLE IF EXISTS addresses CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers_3nf CASCADE;

CREATE TABLE customers_3nf (
    customer_id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    UNIQUE (customer_name, customer_email, customer_phone)
);

CREATE TABLE addresses (
    address_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers_3nf(customer_id),
    address TEXT NOT NULL,
    UNIQUE (customer_id, address)
);

CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE
);

CREATE TABLE products_3nf (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    product_price NUMERIC NOT NULL,
    UNIQUE (product_name, product_price)
);

CREATE TABLE orders_3nf (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers_3nf(customer_id),
    address_id INTEGER NOT NULL REFERENCES addresses(address_id),
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    total_amount NUMERIC NOT NULL
);

CREATE TABLE order_items_3nf (
    order_id INTEGER NOT NULL REFERENCES orders_3nf(order_id),
    product_id INTEGER NOT NULL REFERENCES products_3nf(product_id),
    quantity INTEGER NOT NULL,
    price_at_order NUMERIC NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO customers_3nf (
    customer_name,
    customer_email,
    customer_phone
)
SELECT DISTINCT
    customer_name,
    customer_email,
    customer_phone
FROM customers;

INSERT INTO addresses (
    customer_id,
    address
)
SELECT DISTINCT
    c3.customer_id,
    c2.delivery_address
FROM customers c2
JOIN customers_3nf c3
  ON c3.customer_name = c2.customer_name
 AND c3.customer_email = c2.customer_email
 AND c3.customer_phone = c2.customer_phone;

INSERT INTO categories (category_name)
VALUES
    ('Компьютерная техника'),
    ('Периферия'),
    ('Аксессуары');

INSERT INTO products_3nf (
    product_name,
    category_id,
    product_price
)
SELECT
    p.product_name,
    CASE
        WHEN p.product_name = 'Ноутбук' THEN
            (SELECT category_id FROM categories WHERE category_name = 'Компьютерная техника')
        WHEN p.product_name IN ('Монитор', 'Клавиатура', 'Мышь') THEN
            (SELECT category_id FROM categories WHERE category_name = 'Периферия')
        ELSE
            (SELECT category_id FROM categories WHERE category_name = 'Аксессуары')
    END AS category_id,
    p.product_price
FROM products p;

INSERT INTO orders_3nf (
    order_id,
    customer_id,
    address_id,
    order_date,
    status,
    total_amount
)
SELECT
    o.order_id,
    c3.customer_id,
    a.address_id,
    o.order_date,
    o.status,
    o.total_amount
FROM orders o
JOIN customers c2
  ON c2.customer_id = o.customer_id
JOIN customers_3nf c3
  ON c3.customer_name = c2.customer_name
 AND c3.customer_email = c2.customer_email
 AND c3.customer_phone = c2.customer_phone
JOIN addresses a
  ON a.customer_id = c3.customer_id
 AND a.address = c2.delivery_address;

INSERT INTO order_items_3nf (
    order_id,
    product_id,
    quantity,
    price_at_order
)
SELECT
    oi.order_id,
    p3.product_id,
    oi.product_quantity,
    p.product_price
FROM order_items oi
JOIN products p
  ON p.product_id = oi.product_id
JOIN products_3nf p3
  ON p3.product_name = p.product_name
 AND p3.product_price = p.product_price;