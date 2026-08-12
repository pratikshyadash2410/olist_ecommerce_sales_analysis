import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import google.generativeai as genai
import os
from build_database import build_database
import datetime

# --- CONFIGURATION ---
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

# --- HELPER FUNCTIONS ---
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

def sanitize_column_name(col):
    """Sanitizes names for Altair compliance (SUM(i.total) -> SUM_i_total)."""
    return col.replace('.', '_').replace('(', '_').replace(')', '_').strip()


# ---------------------------------------------------------
# Step 3: Updated Visualization Engine (Priority Detection Fix)
# ---------------------------------------------------------
def render_visualization(df_result):
    """Auto-picks the right chart type based on prioritized column name detection
    and robust data transformations."""
    if df_result.empty:
        st.info("No rows returned, nothing to chart.")
        return

    st.subheader("3. Data Visualization")

    try:
        # Step 0: Sanitize column names right away to prevent visualization library failures
        df_plot = df_result.copy()
        safe_col_map = {col: sanitize_column_name(col) for col in df_plot.columns}
        df_plot.rename(columns=safe_col_map, inplace=True)
        
        # Step 1: Detect explicit types
        numeric_cols = df_plot.select_dtypes(include=["number"]).columns.tolist()
        other_cols = df_plot.select_dtypes(exclude=["number"]).columns.tolist()

        # ---------------------------------------------------------
        # THE FIX: Priority Trend Detection Logic
        # ---------------------------------------------------------
        potential_time_col = None
        
        # Priority A: Look for explicit time period names (month, year, period, date)
        # SQLite's strftime often names the aggregate column one of these.
        for col in df_plot.columns:
            if any(x in col.lower() for x in ['month', 'year', 'date', 'period', 'day']):
                potential_time_col = col
                break
        
        # Priority B: Fall back to checking standard non-numeric columns if inference fails.
        if not potential_time_col and other_cols:
            for col in other_cols:
                parsed = pd.to_datetime(df_plot[col], errors="coerce")
                if parsed.notna().mean() > 0.8:  # most values parse correctly as dates
                    potential_time_col = col
                    break

        # Step 2: Render Chart Based on Detected Shape

        # 1. KPI (Single Value)
        if len(other_cols) == 0 and len(df_plot) == 1:
            for col in df_plot.columns:
                st.metric(label=col.replace('_', ' ').title(), value=df_plot[col].iloc[0])

        # 2. Line Chart (Trend Over Time - THE FIX)
        elif potential_time_col and numeric_cols:
            date_axis = potential_time_col
            y_axis = numeric_cols[0]
            
            # THE MANDATORY TRANSFORMATION: 
            # We must explicitly convert the date strings (strftime output: '2018-05') 
            # into true DATETIME objects. This is crucial for chronological sorting.
            try:
                # Force datetime conversion
                df_plot[date_axis] = pd.to_datetime(df_plot[date_axis])
                
                # Sort Chronologically (mandatory for meaningful lines)
                df_trend = df_plot[[date_axis] + numeric_cols].copy()
                df_trend = df_trend.dropna(subset=[date_axis]).sort_values(date_axis)
                
                # Explicit Altair Line Chart Definition with Temporal Encoding (:T)
                line_chart = (
                    alt.Chart(df_trend)
                    .mark_line(point=True) # Line with small points for clarity
                    .encode(
                        x=alt.X(f"{date_axis}:T", title=date_axis.replace('_', ' ').title()), # :T means Time data
                        y=alt.Y(f"{y_axis}:Q", title=y_axis.replace('_', ' ').title()), # :Q means Quantitative data
                        tooltip=[
                            alt.Tooltip(f"{date_axis}:T", format="%Y-%m-%d"), 
                            alt.Tooltip(f"{y_axis}:Q", format=",.2f") # formatted numeric tooltip
                        ]
                    )
                    .interactive() # Enable zoom/pan
                    .properties(height=400) # Ensure a decent height
                )
                
                st.altair_chart(line_chart, use_container_width=True)
                
            except Exception as e:
                # Fallback to bar chart if date conversion fails (handles edge case)
                st.warning(f"Chronological data found ({date_axis}), but explicit date parsing failed ({e}). Rendering standard chart.")
                chart_df = df_plot.groupby(date_axis)[y_axis].sum().reset_index()
                bar_chart = (
                    alt.Chart(chart_df)
                    .mark_bar()
                    .encode(
                        x=alt.X(f"{date_axis}:N", sort="-y"),
                        y=alt.Y(f"{y_axis}:Q"),
                    )
                )
                st.altair_chart(bar_chart, use_container_width=True)

        # 3. Bar Chart (Categorical Comparison - Working as intended)
        elif other_cols and numeric_cols:
            category_col = other_cols[0]
            value_col = numeric_cols[0]
            
            # Use explicit grouping and top N for reliable bar charts
            chart_df = (
                df_plot.groupby(category_col)[value_col]
                .sum()
                .sort_values(ascending=False)
                .head(15)
                .reset_index()
            )
            # Explicit Altair sorting is mandatory here
            bar_chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X(f"{category_col}:N", sort="-y", title=category_col),
                    y=alt.Y(f"{value_col}:Q", title=value_col),
                )
            )
            st.altair_chart(bar_chart, use_container_width=True)

        # 4. Scatter (Relationship)
        elif len(numeric_cols) >= 2:
            st.scatter_chart(df_plot[numeric_cols[:2]])

        else:
            st.info("This result doesn't map cleanly to a chart — see the table above.")

    except Exception as chart_error:
        st.warning(f"Couldn't generate a chart for this result. It might have complex data relationships. ({chart_error})")


# --- USER INPUT SECTION ---
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
        st.error("Database has no tables. Delete olist.db and reload this page to rebuild.")
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
            # Standard cleanup of fences if Gemini added them
            clean_sql = sql_response_text.strip().replace("```sql", "").replace("```", "").strip()

        st.subheader("1. Generated SQL Query")
        st.code(clean_sql, language="sql")

        # Step 2: Execute Query
        conn = sqlite3.connect(DB_PATH)
        df_result = pd.read_sql_query(clean_sql, conn)
        conn.close()

        st.subheader("2. Query Output Data")
        st.dataframe(df_result)

        # Step 3: Fixed Visualization (Isolated try block)
        render_visualization(df_result)

        # Step 4: Business Insights
        if not df_result.empty:
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