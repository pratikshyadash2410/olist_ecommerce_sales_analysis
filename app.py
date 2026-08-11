import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import google.generativeai as genai

# Page Configuration
st.set_page_config(page_title="Olist AI Data Assistant", layout="wide")
st.title("🤖 Olist E-Commerce AI Data Assistant")
st.write("Ask business questions in plain English — AI converts to SQL, runs it, visualizes data and explains results.")

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
    conn = sqlite3.connect("olist.db")
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
        numeric_cols = df_result.select_dtypes(include=["number"]).columns.tolist()
        other_cols = df_result.select_dtypes(exclude=["number"]).columns.tolist()

        # Detect a date/time-like column among the non-numeric ones
        date_col = None
        for col in other_cols:
            parsed = pd.to_datetime(df_result[col], errors="coerce")
            if parsed.notna().mean() > 0.8:  # most values parse as dates
                date_col = col
                break

        if len(df_result) == 1 and len(df_result.columns) <= 2:
            # Single-value answer, e.g. "what is total revenue?" -> KPI, not a chart
            for col in df_result.columns:
                st.metric(label=col, value=df_result[col].iloc[0])

        elif date_col and numeric_cols:
            # Time-based question -> line chart shows the trend
            chart_df = df_result[[date_col] + numeric_cols].copy()
            chart_df[date_col] = pd.to_datetime(chart_df[date_col], errors="coerce")
            chart_df = chart_df.dropna(subset=[date_col]).sort_values(date_col)
            chart_df = chart_df.set_index(date_col)
            st.line_chart(chart_df)

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
                    x=alt.X(f"{category_col}:N", sort="-y", title=category_col),
                    y=alt.Y(f"{value_col}:Q", title=value_col),
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
    "Which product category has the most orders?",
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

    sql_prompt = f"""
    You are an expert SQL analyst. Convert the user question into a valid SQLite query based on this database schema:

    {schema_info}

    Rules:
    - Output ONLY raw executable SQL code.
    - Do NOT wrap in ```sql or markdown fences.
    - User Question: {user_query}
    """

    try:
        with st.spinner("🤖 Converting your question to SQL..."):
            sql_response_text = generate_with_fallback(sql_prompt)
            clean_sql = sql_response_text.strip().replace("```sql", "").replace("```", "").strip()

        st.subheader("1. Generated SQL Query")
        st.code(clean_sql, language="sql")

        # Step 2: Execute Query
        conn = sqlite3.connect("olist.db")
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

        Acting as a Business Analyst, provide a concise 2-sentence business insight based strictly on these query results.
        """

        with st.spinner("💡 Analyzing results and generating insights..."):
            insight_response_text = generate_with_fallback(insight_prompt)

        st.subheader("4. AI Business Insight")
        st.success(insight_response_text)

    except Exception as e:
        st.error(f"Error executing query: {e}")