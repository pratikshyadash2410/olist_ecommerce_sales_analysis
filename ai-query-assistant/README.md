# AI-Powered Data Query Assistant (Olist Extension)

An extension of my [Olist E-Commerce Sales Analysis](../) project — instead of manually writing SQL to explore the data, this tool lets anyone ask a business question in plain English and get an AI generated SQL query, the result data, an auto picked visualization and a plain English business insight.

## Demo

🔗 **Try it live:** [olist-ai-assistant.streamlit.app](https://olist-ai-assistant.streamlit.app) — type your own business question and see it work end to end

## What it does

1. **Ask a question** in plain English (e.g. *"which 5 states generate the highest revenue?"*)
2. **AI converts it to SQL** using the Google Gemini API, based on the database schema
3. **Query runs** against the Olist SQLite database 
4. **Chart auto-generates**, adapting to the shape of the result
5. **AI generates a concise 5-sentence business insight** summarizing what the result means

## Why I built this

My original Olist project used SQL + Tableau to answer fixed business questions. This extension explores a different angle, making the same underlying data queryable by *anyone*, not just someone who knows SQL which is a growing real world use case in business analytics (natural-language-to-SQL tools, AI assisted BI).

## Tech stack

- **Python** — core logic
- **Streamlit** — web interface
- **SQLite** — local database (built from the Olist Kaggle dataset)
- **Google Gemini API** — natural language → SQL conversion and insight generation
- **Altair** — adaptive charting (KPI / pie / bar / line / scatter, chosen automatically)
- **sqlparse** — formats the generated SQL for readability


## Running it locally

```bash
# 1. Clone this repo and navigate to this folder
cd ai-query-assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app — it builds olist.db automatically from the CSVs in data/ on first launch
streamlit run app.py
```

The `data/` folder already includes the core Olist CSVs (customers, orders, order items, payments, reviews, products, sellers, category translations). The geolocation dataset is excluded — it's not used by this app. If you want it, download it separately from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place it in `data/`, then delete `olist.db` and re-run the app to rebuild.

You'll need a free Gemini API key from [Google AI Studio](https://aistudio.google.com) to use this application.
