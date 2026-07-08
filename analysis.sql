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

CREATE TABLE reviews (
    review_id VARCHAR(50),
    order_id VARCHAR(50),
    review_score INT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP,

    FOREIGN KEY (order_id)
    REFERENCES orders(order_id)
);

CREATE TABLE sellers (
    seller_id VARCHAR(50) PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(20),
    seller_city VARCHAR(100),
    seller_state VARCHAR(10)
);

CREATE TABLE product_category_name_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100)
);

-- ==========================================================
-- Data Quality Checks
-- ==========================================================

-- Products with Missing Category
SELECT
    COUNT(*) AS products_without_category
FROM products
WHERE product_category_name IS NULL;

-- Orders Without Payment Records
SELECT
    COUNT(*) AS orders_without_payment
FROM orders o
LEFT JOIN payments p
ON o.order_id = p.order_id
WHERE p.order_id IS NULL;

-- Customer Identity Check
SELECT
    customer_unique_id,
    COUNT(customer_id) AS customer_records
FROM customers
GROUP BY customer_unique_id
HAVING COUNT(customer_id) > 1
ORDER BY customer_records DESC;

-- Orders Missing Delivery Date
SELECT COUNT(*) AS missing_delivery_records
FROM orders
WHERE order_delivered_customer_date IS NULL;

-- Delivered Orders Missing Approval Timestamp
SELECT COUNT(*) AS delivered_without_approval
FROM orders
WHERE order_status = 'delivered'
AND order_approved_at IS NULL;

-- Freight Cost Greater Than Product Price
SELECT COUNT(*) AS freight_higher_than_price
FROM order_items
WHERE freight_value > price;

-- Order Status Distribution
SELECT
    order_status,
    COUNT(*) AS total_orders
FROM orders
GROUP BY order_status
ORDER BY total_orders DESC;

-- ==========================================================
-- Business Overview
-- ==========================================================

-- Total Revenue Generated
SELECT ROUND(SUM(payment_value), 2) AS total_revenue
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

-- Average Revenue Per Customer
SELECT
    ROUND(
        SUM(payment_value) /
        COUNT(DISTINCT o.customer_id),
        2
    ) AS average_revenue_per_customer
FROM payments p
JOIN orders o
ON p.order_id = o.order_id;

-- Monthly Revenue Trend
SELECT
    DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
    ROUND(SUM(p.payment_value), 2) AS revenue
FROM orders o
JOIN payments p
ON o.order_id = p.order_id
GROUP BY month
ORDER BY month;

-- Yearly Revenue Trend
SELECT
    EXTRACT(YEAR FROM o.order_purchase_timestamp) AS year,
    ROUND(
        SUM(p.payment_value),
        2
) AS revenue
FROM orders o
JOIN payments p
ON o.order_id = p.order_id
GROUP BY year
ORDER BY year;

-- Revenue by Payment Type
SELECT payment_type,
COUNT(*) AS transactions,
ROUND(SUM(payment_value),2) AS revenue
FROM payments
GROUP BY payment_type
ORDER BY revenue DESC;

-- ==========================================================
-- Customer Analysis
-- ==========================================================

-- Geographic Revenue Distribution
SELECT c.customer_state, ROUND(SUM(p.payment_value),2) AS revenue
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
JOIN payments p
ON o.order_id = p.order_id
GROUP BY c.customer_state
ORDER BY revenue DESC
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
    SELECT c.customer_unique_id,
    COUNT(DISTINCT o.order_id) AS order_count
    FROM customers c
    JOIN orders o
    ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
) t
GROUP BY customer_type;

-- Top 10 Highest Spending Customers
SELECT c.customer_unique_id,
ROUND(SUM(p.payment_value),2) AS lifetime_value
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
JOIN payments p
ON o.order_id = p.order_id
GROUP BY c.customer_unique_id
ORDER BY lifetime_value DESC
LIMIT 10;

-- Top Cities by Revenue
SELECT c.customer_city,
ROUND(SUM(p.payment_value),2) AS revenue
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
JOIN payments p
ON o.order_id = p.order_id
GROUP BY c.customer_city
ORDER BY revenue DESC
LIMIT 10;

-- Average Order Value by State
SELECT c.customer_state,
ROUND(
        AVG(p.payment_value),
        2
     ) AS avg_order_value
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
JOIN payments p
ON o.order_id = p.order_id
GROUP BY c.customer_state
HAVING COUNT(*) > 100
ORDER BY avg_order_value DESC;

-- ==========================================================
-- Product Analysis
-- ==========================================================

-- Top Revenue Categories
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(SUM(oi.price), 2) AS revenue
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
ORDER BY revenue DESC
LIMIT 10;

-- Best Selling Categories
SELECT
    pct.product_category_name_english AS product_category,
    COUNT(*) AS total_items_sold
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
ORDER BY total_items_sold DESC
LIMIT 10;

-- Premium Product Categories
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(AVG(oi.price), 2) AS avg_product_price
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY avg_product_price DESC
LIMIT 10;

-- Highest Freight Cost Categories
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(AVG(oi.freight_value), 2) AS avg_freight_cost
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY avg_freight_cost DESC
LIMIT 10;

-- Freight Burden by Category
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(
        AVG((oi.freight_value / oi.price) * 100),
        2
    ) AS freight_percentage
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
WHERE oi.price > 0
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY freight_percentage DESC
LIMIT 10;

-- Average Product Weight by Category
SELECT
    pct.product_category_name_english,
    ROUND(AVG(p.product_weight_g),2) AS avg_weight_g
FROM products p
JOIN product_category_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY avg_weight_g DESC
LIMIT 10;


-- ==========================================================
-- Seller Analysis
-- ==========================================================

-- Top Revenue Generating Sellers
SELECT oi.seller_id,
ROUND(SUM(oi.price),2) AS revenue
FROM order_items oi
GROUP BY oi.seller_id
ORDER BY revenue DESC
LIMIT 10;

-- Average Order Value by Seller
SELECT seller_id,
ROUND(AVG(price),2) AS average_order_value
FROM order_items
GROUP BY seller_id
HAVING COUNT(*) > 50
ORDER BY average_order_value DESC
LIMIT 10;

-- Seller Product Diversity
SELECT seller_id,
COUNT(DISTINCT product_id) AS unique_products
FROM order_items
GROUP BY seller_id
ORDER BY unique_products DESC
LIMIT 10;

-- ==========================================================
-- Payment Analysis
-- ==========================================================

-- Revenue by Payment Method
SELECT payment_type,
COUNT(*) AS total_transactions,
ROUND(SUM(payment_value),2) AS total_revenue
FROM payments
GROUP BY payment_type
ORDER BY total_revenue DESC;

-- Revenue by Installment Plans
SELECT payment_installments,
ROUND(SUM(payment_value),2) AS revenue
FROM payments
GROUP BY payment_installments
ORDER BY revenue DESC;

-- Orders Using Multiple Payments
SELECT order_id,
COUNT(payment_sequential) AS payment_count
FROM payments
GROUP BY order_id
HAVING COUNT(payment_sequential) > 1
ORDER BY payment_count DESC;

-- ==========================================================
-- Delivery Analysis
-- ==========================================================

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

-- Average Order Approval Time
SELECT
    ROUND(
    AVG(
        order_approved_at - order_purchase_timestamp
        ) / INTERVAL '1 day',
        2
    ) AS avg_approval_days
FROM orders
WHERE order_approved_at IS NOT NULL;

-- Average Carrier Dispatch Time
SELECT
    ROUND(
    AVG(
        order_delivered_carrier_date -
        order_approved_at
        ) / INTERVAL '1 day',
        2
    ) AS avg_dispatch_days
FROM orders
WHERE order_delivered_carrier_date IS NOT NULL
AND order_approved_at IS NOT NULL;

-- Late Delivery Percentage
SELECT
    ROUND(
        100.0 *
        COUNT(
            CASE
                WHEN order_delivered_customer_date >
                     order_estimated_delivery_date
                THEN 1
            END
        ) / COUNT(*),
        2
    ) AS late_delivery_percentage
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

-- ==========================================================
-- Customer Review Analysis
-- ==========================================================

-- Rating Distribution
SELECT review_score, COUNT(*) AS total_reviews
FROM reviews
GROUP BY review_score
ORDER BY review_score DESC;

-- Average Rating by Product Category
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(AVG(r.review_score), 2) AS average_rating
FROM reviews r
JOIN orders o
ON r.order_id = o.order_id
JOIN order_items oi
ON o.order_id = oi.order_id
JOIN products p
ON oi.product_id = p.product_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY average_rating DESC;

-- Delivery Delay vs Customer Rating
SELECT
    CASE
        WHEN o.order_delivered_customer_date >
             o.order_estimated_delivery_date
        THEN 'Late Delivery'
        ELSE 'On-Time Delivery'
    END AS delivery_status,
    ROUND(AVG(r.review_score),2) AS average_rating
FROM orders o
JOIN reviews r
ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY delivery_status;

-- State-wise Customer Ratings
SELECT c.customer_state,
ROUND(AVG(r.review_score),2) AS average_rating
FROM customers c
JOIN orders o
ON c.customer_id = o.customer_id
JOIN reviews r
ON o.order_id = r.order_id
GROUP BY c.customer_state
HAVING COUNT(*) > 100
ORDER BY average_rating DESC;

-- ==========================================================
-- Key Business Insights
-- ==========================================================

-- High Revenue but Low Rated Categories
SELECT
    pct.product_category_name_english AS product_category,
    ROUND(SUM(oi.price), 2) AS revenue,
    ROUND(AVG(r.review_score), 2) AS average_rating
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
JOIN orders o
ON oi.order_id = o.order_id
JOIN reviews r
ON o.order_id = r.order_id
JOIN product_category_name_translation pct
ON p.product_category_name = pct.product_category_name
GROUP BY pct.product_category_name_english
HAVING COUNT(*) > 100
ORDER BY revenue DESC, average_rating ASC
LIMIT 10;

-- High Revenue States with Slow Delivery
SELECT c.customer_state,
ROUND(SUM(p.payment_value),2) AS revenue,
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
JOIN payments p
ON o.order_id = p.order_id
WHERE o.order_status='delivered'
GROUP BY c.customer_state
HAVING COUNT(*) > 100
ORDER BY revenue DESC;

-- Seller Revenue vs Customer Rating
SELECT oi.seller_id,
ROUND(SUM(oi.price),2) AS revenue,
ROUND(AVG(r.review_score),2) AS average_rating
FROM order_items oi
JOIN orders o
ON oi.order_id=o.order_id
JOIN reviews r
ON o.order_id=r.order_id
GROUP BY oi.seller_id
HAVING COUNT(*)>50
ORDER BY revenue DESC;

-- Premium Product Categories
SELECT pct.product_category_name_english,
ROUND(AVG(oi.price),2) AS avg_price,
ROUND(AVG(r.review_score),2) AS avg_rating
FROM products p
JOIN product_category_translation pct
ON p.product_category_name=pct.product_category_name
JOIN order_items oi
ON p.product_id=oi.product_id
JOIN orders o
ON oi.order_id=o.order_id
JOIN reviews r
ON o.order_id=r.order_id
GROUP BY pct.product_category_name_english
HAVING COUNT(*)>100
ORDER BY avg_price DESC, avg_rating DESC;

-- Weekend vs Weekday Orders
SELECT
CASE
WHEN EXTRACT(DOW FROM order_purchase_timestamp) IN (0,6)
THEN 'Weekend'
ELSE 'Weekday'
END AS purchase_day,
COUNT(*) AS total_orders
FROM orders
GROUP BY purchase_day;

-- Revenue by Delivery Status
SELECT
CASE
WHEN o.order_delivered_customer_date >
o.order_estimated_delivery_date
THEN 'Late'
ELSE 'On-Time'
END AS delivery_status,
ROUND(SUM(p.payment_value),2) AS revenue
FROM orders o
JOIN payments p
ON o.order_id=p.order_id
WHERE o.order_status='delivered'
GROUP BY delivery_status;

-- END --