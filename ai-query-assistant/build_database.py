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
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(BASE_DIR, "olist.db")

# Checked in order (most specific first) — first keyword match wins.
# This works regardless of exact filename, e.g. "customers.csv",
# "olist_customers_dataset.csv", and "customer_data.csv" all match "customers".
TABLE_KEYWORDS = [
    ("order_items", ["order_item", "orderitem"]),
    ("order_payments", ["order_payment", "payment"]),
    ("order_reviews", ["order_review", "review"]),
    ("category_translation", ["category_translation", "category_name"]),
    ("customers", ["customer"]),
    ("products", ["product"]),
    ("sellers", ["seller"]),
    ("geolocation", ["geo"]),
    ("orders", ["order"]),  # checked last — "order" is a substring of the above too
]


def build_database():
    conn = sqlite3.connect(DB_NAME)

    if not os.path.isdir(DATA_DIR):
        print(f"data/ folder not found at {DATA_DIR}")
        conn.close()
        return

    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    matched_tables = set()

    for csv_path in csv_files:
        filename_lower = os.path.basename(csv_path).lower()
        for table_name, keywords in TABLE_KEYWORDS:
            if table_name in matched_tables:
                continue
            if any(keyword in filename_lower for keyword in keywords):
                df = pd.read_csv(csv_path)

                # Pre-compute reliable 'YYYY-MM' columns for date fields in the
                # orders table using pandas — this avoids depending on SQLite's
                # strftime(), which can behave inconsistently across servers.
                if table_name == "orders":
                    for date_col in ["order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date"]:
                        if date_col in df.columns:
                            parsed = pd.to_datetime(df[date_col], errors="coerce")
                            df[f"{date_col}_year_month"] = parsed.dt.strftime("%Y-%m")

                df.to_sql(table_name, conn, if_exists="replace", index=False)
                print(f"Loaded {table_name}: {len(df)} rows, {len(df.columns)} columns (from {os.path.basename(csv_path)})")
                matched_tables.add(table_name)
                break

    all_table_names = [t for t, _ in TABLE_KEYWORDS]
    missing = [t for t in all_table_names if t not in matched_tables and t != "geolocation"]
    if missing:
        print(f"Could not find matching CSVs for: {missing}")

    conn.close()
    print(f"\nDatabase ready: {DB_NAME}")


if __name__ == "__main__":
    build_database()