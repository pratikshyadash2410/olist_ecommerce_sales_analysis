# AI-Powered Data Query Assistant (Olist Extension)

An extension of my [Olist E-Commerce Sales Analysis](../) project — instead of manually writing SQL to explore the data, this tool lets anyone ask a business question in plain English and get an AI-generated SQL query, the result data, an auto picked visualization and a plain English business insight.

## What it does

1. **Ask a question** in plain English (e.g. *"which state has the highest revenue?"*)
2. **AI converts it to SQL** using the Google Gemini API, based on the database schema
3. **Query runs** against the Olist SQLite database
4. **Chart auto-generates**, adapting to the shape of the result — a KPI for single values, a bar chart for category comparisons, a line chart for trends over time
5. **AI generates a 2-sentence business insight** summarizing what the result means

## Why I built this

My original Olist project used SQL + Tableau to answer fixed business questions. This extension explores a different angle: making the same underlying data queryable by *anyone*, not just someone who knows SQL — which is a growing real world use case in business analytics (natural language to SQL tools, AI assisted BI).

## Tech stack

- **Python** — core logic
- **Streamlit** — web interface
- **SQLite** — local database (built from the Olist Kaggle dataset)
- **Google Gemini API** — natural language → SQL conversion and insight generation
- **Altair** — adaptive charting

## Example questions to try

- "Which state has the highest revenue?"
- "Show monthly order trends over time"
- "What is the average order value?"
- "Top 10 product categories by number of orders"

## Running it locally

```bash
# 1. Clone this repo and navigate to this folder
cd ai-query-assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the Olist dataset from Kaggle and place the CSVs in a `data/` folder
#    https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

# 4. Build the local database
python build_database.py

# 5. Run the app
streamlit run app.py
```

You'll need a free Gemini API key from [Google AI Studio](https://aistudio.google.com) 


## Related

- Main analysis: [Olist E-Commerce Sales Analysis](../) (SQL + Tableau)

