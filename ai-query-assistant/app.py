import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import google.generativeai as genai
import os
from build_database import build_database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "olist.db")

# Page Configuration
st.set_page_config(page_title="Olist AI Data Assistant", layout="wide")
st.title("🤖 Olist E-Commerce AI Data Assistant")
st.write("Ask business questions in plain English — AI converts to SQL, runs it, visualizes data and explains results.")

# Always rebuild the database fresh on startup — this guarantees correct data
# and avoids any stale/corrupt olist.db lingering from earlier deploy attempts.
with st.spinner("Setting up the database..."):
    build_database()

# Built-in diagnostic panel — shows exactly what's in the database right here,
# no need to dig through server logs.
with st.expander("🔍 Database Debug Info (click to expand)"):
    debug_conn = sqlite3.connect(DB_PATH)
    debug_cursor = debug_conn.cursor()
    debug_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    debug_tables = debug_cursor.fetchall()
    st.write(f"**Tables found:** {[t[0] for t in debug_tables]}")
    for (table,) in debug_tables:
        debug_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = debug_cursor.fetchone()[0]
        st.write(f"- `{table}`: {count} rows")
    try:
        debug_cursor.execute("SELECT order_purchase_timestamp FROM orders LIMIT 3")
        sample_timestamps = debug_cursor.fetchall()
        st.write(f"**Sample order_purchase_timestamp values:** {sample_timestamps}")
    except Exception as e:
        st.write(f"Could not read order_purchase_timestamp: {e}")
    debug_conn.close()

# Sidebar for API Key
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter your Gemini API Key:", type="password")

if not api_key:
    st.warning("👈 Please enter your free Gemini API Key in the sidebar to proceed.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=api_key)


def generate_with_fallback(prompt):
    candidate_models = [
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-flash"
    ]
    last_error = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            continue
    raise last_error


def get_db_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    schema_text = ""
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        schema_text += f"Table: {table_name}\nColumns: {', '.join(columns)}\n\n"

    conn.close()
    return schema_text


def render_visualization(df_result):
    """Auto-picks the right chart type based on what the query actually returned,
    so the visualization matches the shape of the business question asked."""
    if df_result.empty:
        st.info("No rows returned, nothing to chart.")
        return

    st.subheader("3. Data Visualization")

    try:
        # Sanitize column names for charting — Vega-Lite treats "." in a field
        # name as nested property access, and chokes on "(" ")" too, so raw
        # SQL aliases like "SUM(t.payment_value)" silently break the chart.
        # Rename to safe names here, but keep the original names as axis titles.
        original_columns = list(df_result.columns)
        safe_names = {
            col: col.replace("(", "_").replace(")", "_").replace(".", "_").replace(" ", "_")
            for col in original_columns
        }
        df_result = df_result.rename(columns=safe_names)
        title_lookup = {safe: original for original, safe in safe_names.items()}

        numeric_cols = df_result.select_dtypes(include=["number"]).columns.tolist()
        other_cols = df_result.select_dtypes(exclude=["number"]).columns.tolist()

        # Detect a date/time-like column among the non-numeric ones
        date_col = None
        for col in other_cols:
            parsed = pd.to_datetime(df_result[col], errors="coerce")
            if parsed.notna().mean() > 0.8:  # most values parse as dates
                date_col = col
                break

        if len(other_cols) == 0 and len(df_result) == 1:
            # Only truly numeric, single-row results count as a KPI
            # (e.g. "what is total revenue?", "average order value")
            for col in df_result.columns:
                st.metric(label=col, value=df_result[col].iloc[0])

        elif date_col and numeric_cols:
            # Time-based question -> line chart shows the trend
            chart_df = df_result[[date_col] + numeric_cols].copy()
            chart_df[date_col] = pd.to_datetime(chart_df[date_col], errors="coerce")
            chart_df = chart_df.dropna(subset=[date_col]).sort_values(date_col)
            value_col = numeric_cols[0]
            line_chart = (
                alt.Chart(chart_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(f"{date_col}:T", title=title_lookup.get(date_col, date_col)),
                    y=alt.Y(f"{value_col}:Q", title=title_lookup.get(value_col, value_col)),
                )
            )
            st.altair_chart(line_chart, use_container_width=True)

        elif other_cols and numeric_cols:
            # Category-based question, e.g. "top states by revenue" -> bar chart
            category_col = other_cols[0]
            value_col = numeric_cols[0]
            chart_df = (
                df_result.groupby(category_col)[value_col]
                .sum()
                .sort_values(ascending=False)
                .head(15)
                .reset_index()
            )
            # st.bar_chart re-sorts categories alphabetically, ignoring our order —
            # use Altair directly and force the x-axis to sort by value (descending)
            bar_chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X(f"{category_col}:N", sort="-y", title=title_lookup.get(category_col, category_col)),
                    y=alt.Y(f"{value_col}:Q", title=title_lookup.get(value_col, value_col)),
                )
            )
            st.altair_chart(bar_chart, use_container_width=True)

        elif len(numeric_cols) >= 2:
            # Two numeric columns, no category -> scatter shows the relationship
            st.scatter_chart(df_result[numeric_cols[:2]])

        else:
            st.info("This result doesn't map cleanly to a chart — see the table above.")

    except Exception as chart_error:
        st.warning(f"Couldn't generate a chart for this result, but your data and insight are still shown. ({chart_error})")


EXAMPLE_QUESTIONS = [
    "Top 10 customer states by revenue",
    "Top 10 product categories by number of orders",
    "Show monthly revenue trend",
    "What is the average order value?",
]

if "user_query" not in st.session_state:
    st.session_state.user_query = "top 10 customer states by revenue"

st.write("**Try an example:**")
example_cols = st.columns(len(EXAMPLE_QUESTIONS))
for col, question in zip(example_cols, EXAMPLE_QUESTIONS):
    if col.button(question, use_container_width=True):
        st.session_state.user_query = question

user_query = st.text_input("Enter your business question:", key="user_query")

if st.button("Analyze Query"):
    schema_info = get_db_schema()

    if not schema_info.strip():
        st.error("Database has no tables. This usually means the CSV filenames in your data/ folder don't match what build_database.py expects. Delete olist.db and reboot the app to rebuild it.")
        data_folder = os.path.join(BASE_DIR, "data")
        try:
            files_found = os.listdir(data_folder)
            st.write(f"**Debug — files found in `data/` folder:** {files_found}")
        except Exception as e:
            st.write(f"**Debug — couldn't read `data/` folder:** {e}")
        st.stop()

    sql_prompt = f"""
    You are an expert SQL analyst. Convert the user question into a valid SQLite query based on this database schema:

    {schema_info}

    Rules:
    - Output ONLY raw executable SQL code.
    - Do NOT wrap in ```sql or markdown fences.
    - If the question asks about a trend over time (monthly, yearly, daily, etc.), extract the period using SQLite's strftime function (e.g. strftime('%Y-%m', date_column) AS month), GROUP BY that extracted period, and ORDER BY it chronologically. Never collapse a trend question into a single aggregate row.
    - User Question: {user_query}
    """

    try:
        with st.spinner("🤖 Converting your question to SQL..."):
            sql_response_text = generate_with_fallback(sql_prompt)
            clean_sql = sql_response_text.strip().replace("```sql", "").replace("```", "").strip()

        st.subheader("1. Generated SQL Query")
        st.code(clean_sql, language="sql")

        # Step 2: Execute Query
        conn = sqlite3.connect(DB_PATH)
        df_result = pd.read_sql_query(clean_sql, conn)
        conn.close()

        st.subheader("2. Query Output Data")
        st.dataframe(df_result)

        # Step 3: Visualization — isolated so a chart issue never blocks Step 4 below
        render_visualization(df_result)

        # Step 4: Business Insights
        insight_prompt = f"""
        User Question: "{user_query}"
        Data Results: {df_result.head(10).to_dict(orient='records')}

        Acting as a Business Analyst, provide a concise business insight in exactly 5 lines based strictly on these query results. Each line should be a short, distinct point (e.g. the headline finding, a notable pattern, a possible business implication, a caveat or limitation, and a suggested next step).
        """

        with st.spinner("💡 Analyzing results and generating insights..."):
            insight_response_text = generate_with_fallback(insight_prompt)

        st.subheader("4. AI Business Insight")
        st.success(insight_response_text)

    except Exception as e:
        st.error(f"Error executing query: {e}")