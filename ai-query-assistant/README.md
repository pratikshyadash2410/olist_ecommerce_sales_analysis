# AI-Powered Data Query Assistant (Olist Extension)

*A natural-language interface for the [Olist E-Commerce Sales Analysis](../) project — ask a business question in plain English and get an AI generated SQL query, the result data, an auto picked chart and a plain-English insight.*

**Stack:** Python · Streamlit · SQLite · Google Gemini API · Altair · sqlparse

## Demo

**Try it live:** [olist-ai-assistant.streamlit.app](https://olist-ai-assistant.streamlit.app) — type your own business question and watch it run end to end.

## How It Works

1. **Ask a question** in plain English — e.g. *"which 5 states generate the highest revenue?"*
2. **AI converts it to SQL** using the Google Gemini API, based on the database schema
3. **Query runs** against the Olist SQLite database
4. **Chart auto-generates**, adapting to the shape of the result
5. **AI summarizes the result** in a concise, plain-English business insight

## Why I Built This

The original Olist project used SQL and Tableau to answer a fixed set of business questions. This extension makes the same data queryable by anyone, not just someone who knows SQL — reflecting a growing real world pattern in business analytics: natural-language-to-SQL tools and AI assisted BI.

## Tech Stack

| Tool | Role |
|---|---|
| Python | Core application logic |
| Streamlit | Web interface |
| SQLite | Local database, built from the Olist Kaggle dataset |
| Google Gemini API | Natural language → SQL conversion and insight generation |
| Altair | Adaptive charting (KPI / pie / bar / line / scatter, chosen automatically) |
| sqlparse | Formats generated SQL for readability |

## Running Locally

```bash
# 1. Clone this repo and navigate to this folder
cd ai-query-assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app — it builds olist.db automatically from the CSVs in data/ on first launch
streamlit run app.py
```

The `data/` folder already includes the core Olist CSVs (customers, orders, order items, payments, reviews, products, sellers, category translations). The geolocation dataset is excluded since it isn't used by this app — if you want it, download it separately from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), place it in `data/`, delete `olist.db`, and re-run the app to rebuild.

You'll need a free Gemini API key from [Google AI Studio](https://aistudio.google.com) to use this application.
