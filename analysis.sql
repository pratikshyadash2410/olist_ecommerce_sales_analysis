-- ==========================================================
-- Project      : Olist E-Commerce Sales Analysis
-- Database     : PostgreSQL
-- Dataset      : Olist Brazilian E-Commerce Dataset
-- Author       : Pratikshya Dash
-- ==========================================================

-- Database Creation

CREATE DATABASE olist_ecommerce;

-- Table Creation

CREATE TABLE customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix VARCHAR(20),
    customer_city VARCHAR(100),
    customer_state VARCHAR(10)
);

CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    order_status VARCHAR(30),
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,

    FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id)
);

CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_name_lenght INT,
    product_description_lenght INT,
    product_photos_qty INT,
    product_weight_g FLOAT,
    product_length_cm FLOAT,
    product_height_cm FLOAT,
    product_width_cm FLOAT
);

CREATE TABLE order_items (
    order_id VARCHAR(50),
    order_item_id INT,
    product_id VARCHAR(50),
    seller_id VARCHAR(50),
    shipping_limit_date TIMESTAMP,
    price NUMERIC(10,2),
    freight_value NUMERIC(10,2),

    PRIMARY KEY (order_id, order_item_id),

    FOREIGN KEY (order_id)
    REFERENCES orders(order_id),

    FOREIGN KEY (product_id)
    REFERENCES products(product_id)
);

CREATE TABLE payments (
    order_id VARCHAR(50),
    payment_sequential INT,
    payment_type VARCHAR(50),
    payment_installments INT,
    payment_value NUMERIC(10,2),

    PRIMARY KEY (order_id, payment_sequential),

    FOREIGN KEY (order_id)
    REFERENCES orders(order_id)
);


-- Business Overview

-- Order Status Distribution
SELECT
    order_status,
    COUNT(*) AS total_orders
FROM orders
GROUP BY order_status
ORDER BY total_orders DESC;

-- Missing Delivery Records
SELECT COUNT(*) AS missing_delivery_date
FROM orders
WHERE order_delivered_customer_date IS NULL;

-- Total Revenue Generated
SELECT
    ROUND(SUM(payment_value), 2) AS total_revenue
FROM payments;

-- Total Orders Processed
SELECT COUNT(DISTINCT order_id) AS total_orders
FROM orders;

-- Total Customers
SELECT COUNT(DISTINCT customer_unique_id)
AS total_customers
FROM customers;

-- Average Order Value (AOV)
SELECT
    ROUND(
        SUM(payment_value) / COUNT(DISTINCT order_id),
        2
    ) AS average_order_value
FROM payments;

-- Monthly Revenue Trend
SELECT
    DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
    ROUND(SUM(p.payment_value), 2) AS revenue
FROM orders o
JOIN payments p
    ON o.order_id = p.order_id
GROUP BY month
ORDER BY month;

-- Revenue by Payment Type
SELECT
    payment_type,
    COUNT(*) AS transactions,
    ROUND(SUM(payment_value),2) AS revenue
FROM payments
GROUP BY payment_type
ORDER BY revenue DESC;

-- Peak Order Periods
SELECT
    DATE_TRUNC('month', order_purchase_timestamp) AS month,
    COUNT(*) AS total_orders
FROM orders
GROUP BY month
ORDER BY total_orders DESC
LIMIT 10;


-- Customer Analysis	

-- Geographic Revenue Distribution
SELECT
    c.customer_state,
    ROUND(SUM(p.payment_value),2) AS revenue
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
JOIN payments p
    ON o.order_id = p.order_id
GROUP BY c.customer_state
ORDER BY revenue DESC
LIMIT 10;

-- Geographic Customer Distribution
SELECT
    customer_state,
    COUNT(DISTINCT customer_id) AS customers
FROM customers
GROUP BY customer_state
ORDER BY customers DESC
LIMIT 10;

-- High Value Markets
SELECT
    c.customer_state,
    ROUND(
        SUM(p.payment_value) /
        COUNT(DISTINCT o.order_id),
        2
    ) AS avg_order_value
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
JOIN payments p
    ON o.order_id = p.order_id
GROUP BY c.customer_state
HAVING COUNT(DISTINCT o.order_id) > 100
ORDER BY avg_order_value DESC
LIMIT 10;

-- Repeat vs One Time Customers
SELECT
    CASE
        WHEN order_count = 1 THEN 'One-Time Customer'
        ELSE 'Repeat Customer'
    END AS customer_type,
    COUNT(*) AS customers
FROM (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM customers c
    JOIN orders o
        ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
) t
GROUP BY customer_type;


-- Product Analysis

-- Top Revenue Categories
SELECT
    p.product_category_name,
    ROUND(SUM(oi.price), 2) AS revenue
FROM products p
JOIN order_items oi
    ON p.product_id = oi.product_id
GROUP BY p.product_category_name
ORDER BY revenue DESC
LIMIT 10;

-- Best Selling Categories
SELECT
    p.product_category_name,
    COUNT(*) AS total_items_sold
FROM products p
JOIN order_items oi
    ON p.product_id = oi.product_id
GROUP BY p.product_category_name
ORDER BY total_items_sold DESC
LIMIT 10;

-- Premium Product Categories
SELECT
    p.product_category_name,
    ROUND(AVG(oi.price), 2) AS avg_product_price
FROM products p
JOIN order_items oi
    ON p.product_id = oi.product_id
GROUP BY p.product_category_name
HAVING COUNT(*) > 100
ORDER BY avg_product_price DESC
LIMIT 10;

-- Most Ordered Categories
SELECT
    p.product_category_name,
    COUNT(DISTINCT oi.order_id) AS total_orders
FROM products p
JOIN order_items oi
    ON p.product_id = oi.product_id
GROUP BY p.product_category_name
ORDER BY total_orders DESC
LIMIT 10;


-- Delivery Analysis

-- Average Delivery Time
SELECT
    ROUND(
        AVG(
            order_delivered_customer_date::date -
            order_purchase_timestamp::date
           ),
           2
) AS avg_delivery_days
FROM orders
WHERE order_status = 'delivered';

-- Regional Delivery Efficiency
SELECT
    c.customer_state,
    ROUND(
        AVG(
            o.order_delivered_customer_date::date -
            o.order_purchase_timestamp::date
           ),
           2
) AS avg_delivery_days
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
HAVING COUNT(*) > 100
ORDER BY avg_delivery_days DESC
LIMIT 10;

-- Late Deliveries
SELECT COUNT(*) AS late_orders
FROM orders
WHERE order_status = 'delivered'
AND order_delivered_customer_date >
    order_estimated_delivery_date;

-- States with Highest Late Deliveries
SELECT
    c.customer_state,
    COUNT(*) AS late_orders
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
AND o.order_delivered_customer_date >
    o.order_estimated_delivery_date
GROUP BY c.customer_state
ORDER BY late_orders DESC
LIMIT 10;

-- Delivery Reliability by State
SELECT
    c.customer_state,
    COUNT(
        CASE
            WHEN o.order_delivered_customer_date >
                 o.order_estimated_delivery_date
            THEN 1
        END
    ) AS late_orders,
    COUNT(*) AS delivered_orders,
    ROUND(
        100.0 * COUNT(
            CASE
                WHEN o.order_delivered_customer_date >
                     o.order_estimated_delivery_date
                THEN 1
            END
        ) / COUNT(*),
        2
    ) AS late_delivery_rate
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
HAVING COUNT(*) > 100
ORDER BY late_delivery_rate DESC
LIMIT 10;

-- END --