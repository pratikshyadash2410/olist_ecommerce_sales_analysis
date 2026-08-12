import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import google.generativeai as genai
import os
from build_database import build_database
import datetime

# --- CONFIGURATION & PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "olist.db")

# Page Configuration
st.set_page_config(page_title="Olist AI Data Assistant", layout="wide")
st.title("🤖 Olist E-Commerce AI Data Assistant")
st.write("Ask business questions in plain English — AI converts to SQL, runs it, visualizes data and explains results.")

# Build the database from the bundled CSVs the very first time the app runs
if not os.path.exists(DB_PATH):
    with st.spinner("Setting up the database for the first time (only happens once)..."):
        try:
            build_database()
            if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
                st.success("✅ Database built successfully.")
                st.rerun()
            else:
                st.error("Failed to create database.")
                st.stop()
        except Exception as e:
            st.error(f"Error building database: {e}")
            st.stop()

# Sidebar for API Key
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter your Gemini API Key:", type="password")

if not api_key:
    st.warning("👈 Please enter your free Gemini API Key in the sidebar to proceed.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=api_key)


# --- HELPERS ---
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


# --- VISUALIZATION ENGINE (DEDICATED ALTAIR) ---
def render_visualization(df_result):
    """Auto-picks the right chart type based on what the query actually returned.
    Uses explicit Altair for Bar and Line charts for maximum reliability."""
    if df_result.empty:
        st.info("No rows returned, nothing to chart.")
        return

    st.subheader("3. Data Visualization")

    try:
        # Step 0: Create a safe copy and sanitize column names (dots -> underscores)
        # This is crucial for Altair to avoid "field not found" errors on aggregate names
        df_plot = df_result.copy()
        safe_col_map = {col: col.replace('.', '_') for col in df_plot.columns}
        df_plot.rename(columns=safe_col_map, inplace=True)
        
        # Step 1: Detect column types explicitly from sanitized dataframe
        numeric_cols = df_plot.select_dtypes(include=["number"]).columns.tolist()
        non_numeric_cols = df_plot.select_dtypes(exclude=["number"]).columns.tolist()

        # Isolate the logic to find the trend/time column among non-numeric ones
        potential_trend_col = None
        # Priority 1: If AI named a column explicitly with 'month', 'year', 'day', 'trend'
        for col in df_plot.columns:
            if any(x in col.lower() for x in ['month', 'year', 'day', 'trend', 'date', 'period']):
                potential_trend_col = col
                break
        
        # Priority 2: Try standard date parsing among other non-numeric columns
        if not potential_trend_col and non_numeric_cols:
            for col in non_numeric_cols:
                parsed = pd.to_datetime(df_plot[col], errors="coerce")
                if parsed.notna().mean() > 0.8:  # most values parse as dates
                    potential_trend_col = col
                    break

        # Step 2: Handle Visualization Based on Shape

        # A) KPI (Single Value Result)
        if len(non_numeric_cols) == 0 and len(df_plot) == 1:
            for col in df_plot.columns:
                st.metric(label=col.replace('_', ' ').title(), value=df_plot[col].iloc[0])

        # B) Line Chart (Explicit Altair for Trend Over Time)
        elif potential_trend_col and numeric_cols:
            x_axis = potential_trend_col
            y_axis = numeric_cols[0] # Use first numeric column as metric
            
            # CRITICAL Step: SQLite outputs dates as formatted strings ('2018-05').
            # Streamlit/Altair need them as proper datetime objects for chronological plotting.
            try:
                # Force datetime conversion
                df_plot[x_axis] = pd.to_datetime(df_plot[x_axis])
                
                # Sort Chronologically (mandatory for meaningful lines)
                df_trend = df_plot.dropna(subset=[x_axis]).sort_values(x_axis)
                
                # Explicit Altair Line Chart Definition
                line_chart = (
                    alt.Chart(df_trend)
                    .mark_line(point=True) # Line with small points for clarity
                    .encode(
                        x=alt.X(f"{x_axis}:T", title=x_axis.replace('_', ' ').title()), # :T means Temporal/Time data
                        y=alt.Y(f"{y_axis}:Q", title=y_axis.replace('_', ' ').title()), # :Q means Quantitative data
                        tooltip=[
                            alt.Tooltip(f"{x_axis}:T", format="%Y-%m-%d"), 
                            alt.Tooltip(f"{y_axis}:Q", format=",.2f") # formatted numeric tooltip
                        ]
                    )
                    .interactive() # Enable zoom/pan
                    .properties(height=400) # Ensure a decent height
                )
                
                st.altair_chart(line_chart, use_container_width=True)
                
            except Exception as e:
                st.warning(f"Trend data detected ({x_axis}), but chronological date conversion failed ({e}). Here is a fallback Bar Chart instead.")
                # Fallback to bar if date conversion fails
                chart_df = df_plot.set_index(x_axis)[[y_axis]].sort_index()
                st.bar_chart(chart_df)

        # C) Bar Chart (Explicit Altair for Categorical Comparison)
        elif non_numeric_cols and numeric_cols:
            category_col = non_numeric_cols[0]
            value_col = numeric_cols[0]
            
            # Limit to manageable top categories
            chart_df = (
                df_plot.groupby(category_col)[value_col]
                .sum()
                .sort_values(ascending=False)
                .head(15)
                .reset_index()
            )
            
            # Explicit Altair Bar Chart Definition with proper sorting
            bar_chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X(f"{category_col}:N", sort="-y", title=category_col.replace('_', ' ').title()), # :N means Nominal/Categorical
                    y=alt.Y(f"{value_col}:Q", title=value_col.replace('_', ' ').title()),
                    tooltip=[
                        alt.Tooltip(f"{category_col}:N"), 
                        alt.Tooltip(f"{value_col}:Q", format=",.2f")
                    ]
                )
                .interactive()
                .properties(height=400)
            )
            st.altair_chart(bar_chart, use_container_width=True)

        # D) Scatter Plot (Two Numeric Columns)
        elif len(numeric_cols) >= 2:
            st.scatter_chart(df_plot[numeric_cols[:2]])

        else:
            st.info("This result doesn't map cleanly to a chart — see the table above.")

    except Exception as chart_error:
        st.warning(f"Couldn't generate a chart for this result. It might have complex data relationships. ({chart_error})")


# --- EXAMPLES & USER INPUT ---
EXAMPLE_QUESTIONS = [
    "Top 10 customer states by revenue",
    "Top 10 product categories by number of orders",
    "Show monthly revenue trend",
    "What is the average order value?",
]

if "current_question" not in st.session_state:
    st.session_state.current_question = EXAMPLE_QUESTIONS[0]

st.write("**Try an example:**")
example_cols = st.columns(len(EXAMPLE_QUESTIONS))
for col, question in zip(example_cols, EXAMPLE_QUESTIONS):
    if col.button(question, use_container_width=True):
        st.session_state.current_question = question

user_query = st.text_input("Enter your business question:", key="current_question")

# --- MAIN ANALYSIS LOOP ---
if st.button("Analyze Query"):
    schema_info = get_db_schema()

    if not schema_info.strip():
        st.error("Database has no tables. Delete olist.db and reload this page.")
        st.stop()

    sql_prompt = f"""
    You are an expert SQL analyst. Convert the user question into a valid SQLite query based on this database schema:

    {schema_info}

    Rules:
    - Output ONLY raw executable SQL code.
    - Do NOT wrap in ```sql or markdown fences.
    - If the question asks about a trend over time (monthly, yearly, daily, etc.), extract the period using SQLite's strftime function (e.g. strftime('%Y-%m', date_column) AS period), GROUP BY that extracted period, and ORDER BY it chronologically. Use 'period' or 'date' in the alias name for clarity.
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

        # Step 3: Visualization — explicit Altair integration
        render_visualization(df_result)

        # Step 4: Business Insights
        if not df_result.empty:
            insight_prompt = f"""
            User Question: "{user_query}"
            Data Results: {df_result.head(10).to_dict(orient='records')}

            Acting as a Business Analyst, provide a concise business insight in exactly 5 lines based strictly on these query results. Each line should be a short, distinct point (e.g. headline finding, pattern, implication, caveat, next step).
            """

            with st.spinner("💡 Analyzing results and generating insights..."):
                insight_response_text = generate_with_fallback(insight_prompt)

            st.subheader("4. AI Business Insight")
            st.success(insight_response_text)

    except Exception as e:
        st.error(f"Error executing query: {e}")