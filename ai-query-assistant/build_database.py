"""
Builds olist.db from the raw Olist CSV files.

Usage:
    1. Download the dataset from Kaggle: "Brazilian E-Commerce Public Dataset by Olist"
       https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
    2. Place the CSV files in a folder called `data/` next to this script
       (any reasonable filename works — see TABLE_KEYWORDS below).
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
# Works regardless of exact filename: "customers.csv", "olist_customers_dataset.csv",
# and "customer_data.csv" all correctly match the "customers" table.
TABLE_KEYWORDS = [
    ("order_items", ["order_item", "orderitem"]),
    ("order_payments", ["order_payment", "payment"]),
    ("order_reviews", ["order_review", "review"]),
    ("category_translation", ["category_translation", "category_name"]),
    ("customers", ["customer"]),
    ("products", ["product"]),
    ("sellers", ["seller"]),
    ("geolocation", ["geo"]),
    ("orders", ["order"]),  # checked last — "order" is a substring of several keywords above
]

# Date columns in the orders table that get a pre-computed 'YYYY-MM' column.
# Computed here with pandas (not SQLite's strftime) because strftime's exact
# behavior can vary subtly across different server environments — pre-computing
# with pandas guarantees the same reliable result everywhere the app runs.
ORDER_DATE_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_customer_date",
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
            if not any(keyword in filename_lower for keyword in keywords):
                continue

            df = pd.read_csv(csv_path)

            if table_name == "orders":
                for date_col in ORDER_DATE_COLUMNS:
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