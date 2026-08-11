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

DATA_DIR = "data"
DB_NAME = "olist.db"

FILE_TO_TABLE = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}


def build_database():
    conn = sqlite3.connect(DB_NAME)

    for filename, table_name in FILE_TO_TABLE.items():
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"Missing file: {path} — skipping. Download it from Kaggle first.")
            continue

        df = pd.read_csv(path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"Loaded {table_name}: {len(df)} rows, {len(df.columns)} columns")

    conn.close()
    print(f"\nDatabase ready: {DB_NAME}")


if __name__ == "__main__":
    build_database()
