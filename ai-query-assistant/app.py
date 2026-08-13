import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from google import genai


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Olist AI Data Assistant",
    page_icon="🛒",
    layout="wide",
)

DB_PATH = Path(__file__).parent / "olist.db"
GEMINI_MODEL = "gemini-2.5-flash"


# ============================================================
# DATABASE SCHEMA
# ============================================================

SCHEMA = """
TABLE: customers
- customer_id TEXT
- customer_unique_id TEXT
- customer_zip_code_prefix INTEGER
- customer_city TEXT
- customer_state TEXT

TABLE: geolocation
- geolocation_zip_code_prefix INTEGER
- geolocation_lat REAL
- geolocation_lng REAL
- geolocation_city TEXT
- geolocation_state TEXT

TABLE: orders
- order_id TEXT
- customer_id TEXT
- order_status TEXT
- order_purchase_timestamp TEXT
- order_purchase_timestamp_year_month TEXT -- pre-computed YYYY-MM
- order_approved_at TEXT
- order_delivered_carrier_date TEXT
- order_delivered_customer_date TEXT
- order_estimated_delivery_date TEXT

TABLE: order_items
- order_id TEXT
- order_item_id INTEGER
- product_id TEXT
- seller_id TEXT
- shipping_limit_date TEXT
- price REAL
- freight_value REAL

TABLE: order_payments
- order_id TEXT
- payment_sequential INTEGER
- payment_type TEXT
- payment_installments INTEGER
- payment_value REAL

TABLE: order_reviews
- review_id TEXT
- order_id TEXT
- review_score INTEGER
- review_comment_title TEXT
- review_comment_message TEXT
- review_creation_date TEXT
- review_answer_timestamp TEXT

TABLE: products
- product_id TEXT
- product_category_name TEXT
- product_name_lenght REAL
- product_description_lenght REAL
- product_photos_qty REAL
- product_weight_g REAL
- product_length_cm REAL
- product_height_cm REAL
- product_width_cm REAL

TABLE: sellers
- seller_id TEXT
- seller_zip_code_prefix INTEGER
- seller_city TEXT
- seller_state TEXT

TABLE: product_category_name_translation
- product_category_name TEXT
- product_category_name_english TEXT
"""


# ============================================================
# GEMINI
# ============================================================

def get_gemini_client():
    api_key = st.secrets.get(
        "GEMINI_API_KEY",
        os.getenv("GEMINI_API_KEY")
    )

    if not api_key:
        st.error(
            "GEMINI_API_KEY is missing. Add it in "
            "Streamlit Cloud → Settings → Secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


client = get_gemini_client()


# ============================================================
# SQLITE
# ============================================================

@st.cache_resource
def get_connection():
    return sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False
    )


conn = get_connection()


# ============================================================
# GENERATE SQL
# ============================================================

def generate_sql(question):

    prompt = f"""
You are an expert SQLite data analyst working with the Brazilian
Olist e-commerce dataset.

Convert the user's natural-language question into ONE valid SQLite
SELECT query.

DATABASE SCHEMA:
{SCHEMA}

STRICT RULES:

1. Return ONLY SQL.
2. Do not use markdown code fences.
3. Only generate SELECT or WITH ... SELECT queries.
4. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH,
   DETACH, PRAGMA, VACUUM, or other database-changing commands.
5. Use only tables and columns present in the schema.
6. NEVER use SQLite strftime().
7. NEVER extract month/year from order_purchase_timestamp at query time.
8. For monthly analysis, ALWAYS use:
   orders.order_purchase_timestamp_year_month
9. That column already contains YYYY-MM values.
10. For monthly trends, GROUP BY and ORDER BY the YYYY-MM column.
11. For revenue from products, use order_items.price.
12. When joining orders and order_items, use order_id.
13. When joining orders and customers, use customer_id.
14. When joining order_items and products, use product_id.
15. When joining order_items and sellers, use seller_id.
16. For English category names, join the translation table.
17. Use COUNT(DISTINCT order_id) for order counts when joins may
    duplicate orders.
18. For top-N questions, use ORDER BY and LIMIT.
19. Never invent tables or columns.

MONTHLY ORDER EXAMPLE:

SELECT
    order_purchase_timestamp_year_month AS month,
    COUNT(DISTINCT order_id) AS total_orders
FROM orders
GROUP BY order_purchase_timestamp_year_month
ORDER BY order_purchase_timestamp_year_month;

MONTHLY REVENUE EXAMPLE:

SELECT
    o.order_purchase_timestamp_year_month AS month,
    ROUND(SUM(oi.price), 2) AS revenue
FROM orders o
JOIN order_items oi
    ON o.order_id = oi.order_id
GROUP BY o.order_purchase_timestamp_year_month
ORDER BY o.order_purchase_timestamp_year_month;

USER QUESTION:
{question}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    sql = response.text.strip()

    sql = re.sub(
        r"^```(?:sql)?\s*",
        "",
        sql,
        flags=re.IGNORECASE
    )
    sql = re.sub(r"\s*```$", "", sql)

    return sql.strip()


# ============================================================
# SQL SAFETY
# ============================================================

def validate_sql(sql):

    cleaned = sql.strip().lower()

    if not cleaned:
        return False, "Gemini returned an empty SQL query."

    if not (
        cleaned.startswith("select")
        or cleaned.startswith("with")
    ):
        return False, "Only SELECT queries are allowed."

    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "attach ",
        "detach ",
        "pragma ",
        "vacuum ",
        "replace ",
    ]

    for keyword in forbidden:
        if keyword in cleaned:
            return False, f"Blocked SQL keyword: {keyword.strip()}"

    if "strftime" in cleaned:
        return False, (
            "strftime() is not allowed. Use "
            "order_purchase_timestamp_year_month instead."
        )

    return True, None


# ============================================================
# RUN QUERY
# ============================================================

def execute_sql(sql):

    valid, error = validate_sql(sql)

    if not valid:
        return pd.DataFrame(), error

    try:
        df = pd.read_sql_query(sql, conn)
        return df, None
    except Exception as exc:
        return pd.DataFrame(), str(exc)


# ============================================================
# AI INSIGHT
# ============================================================

def generate_insight(question, df):

    if df.empty:
        return "No data was returned."

    preview = df.head(100).to_string(index=False)

    prompt = f"""
You are a business data analyst.

USER QUESTION:
{question}

QUERY RESULT:
{preview}

Give a concise business insight based ONLY on the supplied result.

Rules:
- Do not invent numbers.
- Mention important trends or comparisons.
- If this is a monthly trend, identify increases, decreases,
  fluctuations, or peaks.
- Keep it to 2-4 bullet points.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text.strip()


# ============================================================
# AUTOMATIC CHART
# ============================================================

def show_chart(df):

    if df.empty or len(df.columns) < 2:
        return

    possible_x = [
        "month",
        "year_month",
        "order_purchase_timestamp_year_month",
        "date",
        "year",
    ]

    x_col = next(
        (col for col in possible_x if col in df.columns),
        None
    )

    if x_col is None:
        return

    numeric_cols = df.select_dtypes(
        include="number"
    ).columns.tolist()

    if not numeric_cols:
        return

    y_col = numeric_cols[0]

    chart_df = df.copy()

    if x_col in [
        "month",
        "year_month",
        "order_purchase_timestamp_year_month"
    ]:
        chart_df[x_col] = pd.to_datetime(
            chart_df[x_col].astype(str),
            format="%Y-%m",
            errors="coerce"
        )
    else:
        chart_df[x_col] = pd.to_datetime(
            chart_df[x_col],
            errors="coerce"
        )

    chart_df = chart_df.dropna(subset=[x_col])
    chart_df = chart_df.sort_values(x_col)

    if chart_df.empty:
        return

    fig = px.line(
        chart_df,
        x=x_col,
        y=y_col,
        markers=True,
        title=f"{y_col.replace('_', ' ').title()} Trend"
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title=y_col.replace("_", " ").title(),
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ============================================================
# APP UI
# ============================================================

st.title("🛒 Olist AI Data Assistant")

st.write(
    "Ask questions about Olist e-commerce data in plain English. "
    "Gemini converts your question into SQL, runs it on SQLite, "
    "and generates a business insight."
)


with st.sidebar:

    st.header("📊 Database")

    st.success("SQLite database connected")

    st.write("9 Olist tables")

    st.divider()

    st.subheader("Try asking:")

    examples = [
        "Show me the monthly order trend",
        "What is the monthly revenue trend?",
        "Which product categories generate the most revenue?",
        "Which states have the most customers?",
        "What are the most common payment methods?",
        "What is the average review score?",
        "Which sellers generate the highest revenue?",
    ]

    for example in examples:
        st.caption(f"• {example}")


question = st.text_input(
    "Ask a business question",
    placeholder="Example: Show me the monthly order trend"
)


if st.button("🔍 Analyze", type="primary"):

    if not question.strip():

        st.warning("Please enter a question.")

    else:

        with st.spinner("🤖 Generating SQL..."):
            sql = generate_sql(question)

        with st.expander("🧠 Generated SQL"):
            st.code(sql, language="sql")

        with st.spinner("📊 Running query..."):
            df, error = execute_sql(sql)

        if error:

            st.error("Query could not be executed.")
            st.code(error)

        elif df.empty:

            st.warning("The query returned no rows.")

        else:

            st.subheader("📋 Results")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            show_chart(df)

            with st.spinner("💡 Generating business insight..."):
                insight = generate_insight(question, df)

            st.subheader("💡 AI Insight")
            st.markdown(insight)