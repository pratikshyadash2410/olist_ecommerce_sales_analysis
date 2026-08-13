import sqlite3
import os
import pandas as pd
import streamlit as st
import altair as alt
import sqlparse
import google.generativeai as genai
from build_database import build_database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "olist.db")

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Olist AI Data Assistant", layout="wide")
st.title("🤖 Olist E-Commerce AI Data Assistant")
st.write("Ask business questions in plain English — AI converts to SQL, runs it, visualizes data, and explains results.")

# Database is rebuilt fresh from the CSVs on every startup — cheap (a few
# seconds) and guarantees correct, up-to-date data regardless of server state.
with st.spinner("Setting up the database..."):
    build_database()

# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter your Gemini API Key:", type="password")

if not api_key:
    st.warning("👈 Please enter your free Gemini API Key in the sidebar to proceed.")
    st.stop()

genai.configure(api_key=api_key)


def generate_with_fallback(prompt):
    candidate_models = [
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-flash",
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
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col[1] for col in cursor.fetchall()]
        schema_text += f"Table: {table_name}\nColumns: {', '.join(columns)}\n\n"

    conn.close()
    return schema_text


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def render_visualization(df_result):
    """Auto-picks the right chart type based on what the query actually
    returned, so the visualization matches the shape of the business
    question asked:
      - purely numeric, single row  -> KPI metric
      - date/time column present    -> line chart (trend)
      - category column, <=5 groups -> pie chart (proportions are clear)
      - category column, >5 groups  -> bar chart (stays readable at scale)
      - two numeric columns only    -> scatter chart
    """
    if df_result.empty:
        st.info("No rows returned, nothing to chart.")
        return

    st.subheader("3. Data Visualization")

    try:
        # Sanitize column names for charting — Vega-Lite treats "." in a
        # field name as nested property access and chokes on "(" ")" too,
        # so raw SQL aliases like "SUM(t.payment_value)" silently break
        # charts. Rename to safe names here; original names still show
        # as axis/tooltip titles via title_lookup.
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
            if parsed.notna().mean() > 0.8:
                date_col = col
                break

        if len(other_cols) == 0 and len(df_result) == 1:
            # Purely numeric, single-row result (e.g. "what is total revenue?")
            for col in df_result.columns:
                raw_value = df_result[col].iloc[0]
                if isinstance(raw_value, (int, float)):
                    display_value = f"{raw_value:,.2f}"
                else:
                    display_value = raw_value
                st.metric(label=title_lookup.get(col, col), value=display_value)

        elif date_col and numeric_cols:
            # Time-based question -> line chart shows the trend
            value_col = numeric_cols[0]
            chart_df = df_result[[date_col, value_col]].copy()
            chart_df[date_col] = pd.to_datetime(chart_df[date_col], errors="coerce")
            chart_df = chart_df.dropna(subset=[date_col]).sort_values(date_col)

            line_chart = (
                alt.Chart(chart_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(f"{date_col}:T", title=title_lookup.get(date_col, date_col)),
                    y=alt.Y(f"{value_col}:Q", title=title_lookup.get(value_col, value_col)),
                    tooltip=[
                        alt.Tooltip(f"{date_col}:T", title=title_lookup.get(date_col, date_col)),
                        alt.Tooltip(f"{value_col}:Q", title=title_lookup.get(value_col, value_col), format=",.2f"),
                    ],
                )
            )
            st.altair_chart(line_chart, use_container_width=True)

        elif other_cols and numeric_cols:
            # Category-based question, e.g. "top states by revenue"
            category_col = other_cols[0]
            value_col = numeric_cols[0]
            chart_df = (
                df_result.groupby(category_col)[value_col]
                .sum()
                .sort_values(ascending=False)
                .head(15)
                .reset_index()
            )
            category_title = title_lookup.get(category_col, category_col)
            value_title = title_lookup.get(value_col, value_col)

            if len(chart_df) <= 5:
                # Few categories -> a pie chart shows proportions clearly
                pie_chart = (
                    alt.Chart(chart_df)
                    .mark_arc(innerRadius=60)
                    .encode(
                        theta=alt.Theta(f"{value_col}:Q"),
                        color=alt.Color(f"{category_col}:N", title=category_title),
                        tooltip=[
                            alt.Tooltip(f"{category_col}:N", title=category_title),
                            alt.Tooltip(f"{value_col}:Q", title=value_title, format=",.2f"),
                        ],
                    )
                )
                st.altair_chart(pie_chart, use_container_width=True)
            else:
                # More categories -> bar chart stays readable at this size.
                # st.bar_chart re-sorts categories alphabetically, ignoring
                # our order, so Altair is used directly with sort="-y".
                bar_chart = (
                    alt.Chart(chart_df)
                    .mark_bar()
                    .encode(
                        x=alt.X(f"{category_col}:N", sort="-y", title=category_title),
                        y=alt.Y(f"{value_col}:Q", title=value_title),
                        tooltip=[
                            alt.Tooltip(f"{category_col}:N", title=category_title),
                            alt.Tooltip(f"{value_col}:Q", title=value_title, format=",.2f"),
                        ],
                    )
                )
                st.altair_chart(bar_chart, use_container_width=True)

        elif len(numeric_cols) >= 2:
            # Two numeric columns, no category -> scatter shows the relationship.
            # zero=False avoids forcing a 0 baseline, which looks wrong for
            # values like month numbers that don't naturally start at 0.
            x_col, y_col = numeric_cols[0], numeric_cols[1]
            scatter_chart = (
                alt.Chart(df_result)
                .mark_circle(size=80)
                .encode(
                    x=alt.X(f"{x_col}:Q", scale=alt.Scale(zero=False), title=title_lookup.get(x_col, x_col)),
                    y=alt.Y(f"{y_col}:Q", scale=alt.Scale(zero=False), title=title_lookup.get(y_col, y_col)),
                    tooltip=[
                        alt.Tooltip(f"{x_col}:Q", title=title_lookup.get(x_col, x_col)),
                        alt.Tooltip(f"{y_col}:Q", title=title_lookup.get(y_col, y_col), format=",.2f"),
                    ],
                )
            )
            st.altair_chart(scatter_chart, use_container_width=True)

        else:
            st.info("This result doesn't map cleanly to a chart — see the table above.")

    except Exception as chart_error:
        st.warning(f"Couldn't generate a chart for this result, but your data and insight are still shown. ({chart_error})")


# ---------------------------------------------------------------------------
# Main query flow
# ---------------------------------------------------------------------------
EXAMPLE_QUESTIONS = [
    "Top 10 customer states by revenue",
    "What are the top 5 payment types used?",
    "Top 10 product categories by revenue",
    "Top 10 sellers by number of orders",
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
        st.error("Database has no tables. Try rebooting the app to rebuild it.")
        st.stop()

    sql_prompt = f"""
    You are an expert SQL analyst. Convert the user question into a valid SQLite query based on this database schema:

    {schema_info}

    Rules:
    - Output ONLY raw executable SQL code.
    - Do NOT wrap in ```sql or markdown fences.
    - If the question involves grouping or displaying data by month or year in any way, and a column ending in '_year_month' exists in the schema (e.g. order_purchase_timestamp_year_month), always use that column directly with GROUP BY and ORDER BY it — do NOT use strftime() and do NOT extract a raw numeric month (e.g. do NOT use strftime('%m', ...) alone). Only use strftime() if no such pre-computed column is available.
    - User Question: {user_query}
    """

    try:
        with st.spinner("🤖 Converting your question to SQL..."):
            sql_response_text = generate_with_fallback(sql_prompt)
            clean_sql = sql_response_text.strip().replace("```sql", "").replace("```", "").strip()

        st.subheader("1. Generated SQL Query")
        formatted_sql = sqlparse.format(clean_sql, reindent=True, keyword_case="upper", indent_width=4)
        st.code(formatted_sql, language="sql")

        conn = sqlite3.connect(DB_PATH)
        df_result = pd.read_sql_query(clean_sql, conn)
        conn.close()

        st.subheader("2. Query Output Data")
        df_display = df_result.copy()
        df_display.index = df_display.index + 1
        st.dataframe(df_display)

        render_visualization(df_result)

        insight_prompt = f"""
        User Question: "{user_query}"
        Data Results: {df_result.head(10).to_dict(orient='records')}

        Acting as a Business Analyst, write a concise, professional insight in exactly 5 sentences as a single flowing paragraph (not bullet points or numbered lines). Cover, in natural analyst commentary: the headline finding, a notable pattern or comparison, a business implication, a caveat or limitation in the data, and a suggested next step.
        """

        with st.spinner("💡 Analyzing results and generating insights..."):
            insight_response_text = generate_with_fallback(insight_prompt)

        st.subheader("4. AI Business Insight")
        st.success(insight_response_text)

    except Exception as e:
        st.error(f"Error executing query: {e}")