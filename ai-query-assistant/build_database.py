"""
Builds olist.db from the raw Olist CSV files.

Usage:
    1. Download the dataset from Kaggle: "Brazilian E-Commerce Public Dataset by Olist"
       https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
    2. Place all the CSV files in a folder called `data/` next to this script.
    3. Run: python build_database.py
"""

import pandas as pd
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(BASE_DIR, "olist.db")

# Each table accepts either the short name or the original Kaggle filename
TABLE_CANDIDATES = {
    "customers": ["customers.csv", "olist_customers_dataset.csv"],
    "geolocation": ["geolocation.csv", "olist_geolocation_dataset.csv"],
    "order_items": ["order_items.csv", "olist_order_items_dataset.csv"],
    "order_payments": ["order_payments.csv", "payments.csv", "olist_order_payments_dataset.csv"],
    "order_reviews": ["order_reviews.csv", "olist_order_reviews_dataset.csv"],
    "orders": ["orders.csv", "olist_orders_dataset.csv"],
    "products": ["products.csv", "olist_products_dataset.csv"],
    "sellers": ["sellers.csv", "olist_sellers_dataset.csv"],
    "category_translation": ["category_translation.csv", "product_category_name_translation.csv"],
}


def build_database():
    conn = sqlite3.connect(DB_NAME)

    for table_name, candidate_filenames in TABLE_CANDIDATES.items():
        found_path = None
        for filename in candidate_filenames:
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                found_path = path
                break

        if not found_path:
            print(f"Missing file for table '{table_name}' — tried: {candidate_filenames}. Skipping.")
            continue

        df = pd.read_csv(found_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"Loaded {table_name}: {len(df)} rows, {len(df.columns)} columns (from {os.path.basename(found_path)})")

    conn.close()
    print(f"\nDatabase ready: {DB_NAME}")


if __name__ == "__main__":
    build_database()
