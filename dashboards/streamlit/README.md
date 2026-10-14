# Streamlit dashboard – SaaS CRM Product Analytics

Interactive three-page dashboard built with Streamlit, Plotly, pandas and the project's SQLite database
(`data/processed/crm_analytics.db`). Nothing is generated or hardcoded: every number is computed from the database using
the definitions in `reports/kpi_definitions.md`, and checked against the SQL result tables by `validate_app.py`.

## Run it (macOS, Apple Silicon or Intel)
From the project root (the folder that contains `README.md`):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboards/streamlit/app.py
```
The browser opens at http://localhost:8501. If the database is missing (`data/processed/crm_analytics.db`), build it first:
`python scripts/generate_data.py && python scripts/run_analysis.py`. Run the command from the project root so the
`.streamlit/config.toml` theme is picked up (paths inside the app are root-relative regardless).

## Structure
```
dashboards/streamlit/
├── app.py                  entry point: sidebar filters, filtered scope, page navigation
├── views/                  product_overview.py · feature_adoption.py · customer_engagement.py
├── crm_dash/
│   ├── data.py             loads SQLite tables (cached by app.py)
│   ├── metrics.py          KPI functions (pure pandas, same definitions as the SQL)
│   ├── charts.py           Plotly figure builders
│   └── ui.py               CSS, KPI cards, notes
├── validate_app.py         validation + headless app test; output in validation_results.txt
└── requirements.txt
```

## Filters and what they affect
| Metric | Plan / industry / size | Date range |
|---|---|---|
| Total accounts / users | applied | accounts/users existing by range end |
| Active users / accounts, Avg DAU, DAU trend | applied | applied |
| MAU, DAU/MAU | applied | last calendar month inside the range (partial months flagged) |
| Feature adoption, usage frequency, usage by plan | applied | applied |
| Engagement by industry / company size, engagement trend | applied | applied (exposure = days inside the range) |
| Activation rate | applied | **not applied** – fixed 14-day cohort (signed up Jan 1–Mar 18) |
| New vs established adoption | applied | **not applied** – fixed 30-day exposure per account |
| Inactive accounts / inactivity rate | applied | **not applied** – fixed: no events in the last 30 days of the window |

Each page states this in the banner under the title. An empty filter selection or an incomplete date range shows a
message instead of misleading numbers.

## Validation
`python dashboards/streamlit/validate_app.py` (output saved in `validation_results.txt`) runs: dashboard metrics vs the
SQL result tables; filtered scopes vs fresh SQL queries; single-segment filters vs the matching SQL rows; date range vs
q01/q02/q03; and a headless run of all three pages with filter changes (Streamlit `AppTest`). It does not test visual
layout. Layout was inspected manually in a browser (see the main README for what was checked).
