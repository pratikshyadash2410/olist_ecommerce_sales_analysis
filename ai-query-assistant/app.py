import sqlite3
import pandas as pd
import streamlit as st
import google.generativeai as genai
import matplotlib
# Force Agg backend BEFORE importing pyplot - Crucial for Streamlit Cloud
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns

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

# ... (rest of your helper functions: generate_with_fallback, get_db_schema) ...

# ---------------------------------------------------------
# Step 3: Updated Robust Cloud Visualization Logic
# ---------------------------------------------------------
def render_visualization(df_result):
    """Auto-picks the right chart type and renders cloud-safely."""
    if df_result.empty:
        st.info("No rows returned, nothing to chart.")
        return

    st.subheader("3. Data Visualization")

    try:
        # 1. Clean Data & Convert Types explicitly
        df_plot = df_result.copy()
        for col in df_plot.columns:
            df_plot[col] = pd.to_numeric(df_plot[col], errors='ignore')
        
        numeric_cols = df_plot.select_dtypes(include=['number']).columns.tolist()
        non_numeric_cols = df_plot.select_dtypes(exclude=['number']).columns.tolist()
        
        # 2. Check Data Shape for Chart Compatibility
        if not numeric_cols or not non_numeric_cols or len(df_plot.columns) < 2:
            st.info("This result doesn't map cleanly to a chart — see the table above.")
            return

        # 3. Cloud-Safe Plotting: Explicit Figure Management
        # Clear any existing plots to prevent overlay issues
        plt.clf() 
        fig, ax = plt.subplots(figsize=(10, 5)) # Use subplots for explicit control
        
        # 4. Standard Categorical Comparison (Bar Chart)
        x_col = non_numeric_cols[0]
        y_col = numeric_cols[0]
        
        # Limit comparison to manageable top rows (e.g., top 10 categories)
        plot_data = df_plot.head(10).sort_values(by=y_col, ascending=False)
        
        # Modern Seaborn approach with explicit object assignment
        sns.barplot(data=plot_data, x=x_col, y=y_col, ax=ax, palette="viridis", edgecolor="black")
        
        # Styling adjustments for readability on the web
        ax.set_title(f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}", fontsize=14)
        ax.set_ylabel(y_col.replace('_', ' ').title())
        ax.set_xlabel(x_col.replace('_', ' ').title())
        
        # Rotate labels so they don't overlap
        plt.xticks(rotation=45, ha='right') 
        plt.tight_layout() # Pre-calculate layout to prevent clipping

        # 5. Render to Streamlit UI
        st.pyplot(fig)
        
        # 6. Explicit Cleanup: Crucial for cloud memory management
        plt.close(fig) 

    except Exception as chart_error:
        st.warning(f"Couldn't generate a chart for this result. It might have complex data relationships. ({chart_error})")

# ... (rest of your app logic: Analyze Query Button, SQL execution, Insights) ...
# Insert your helper functions and main logic loop back here, exactly as you had them before deployment.
# THE KEY CHANGE IS THE `render_visualization` FUNCTION ABOVE.