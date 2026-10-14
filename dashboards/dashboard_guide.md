# Power BI Dashboard Build Guide

Build time: about 60–90 minutes in Power BI Desktop (Windows).

## What is and is not done
| Done in this repo | You must do manually |
|---|---|
| All model tables as CSV (`data/processed/powerbi/`) and SQL result tables (`data/processed/kpi_tables/`) | Open Power BI Desktop, import, create relationships (Section 2) |
| DAX measures (`powerbi_measures.dax`) | Paste the measures (Section 3) |
| Theme file (`theme.json`) | Import the theme, place visuals, set formats (Section 4) |
| Expected value for every visual, checked against SQL: `expected_values.csv` (85 checks via `scripts/validate_dashboard.py`) | Compare each visual with `expected_values.csv` (Section 5) |

**No `.pbix` exists.** Power BI Desktop is Windows-only and was not available. The 85 checks recompute each visual's value
from the model tables with the same logic as the DAX, in Python. They prove the tables and measure logic are right;
they do **not** prove the DAX runs correctly in Power BI. Section 5 is the step where you confirm that.

Only KPIs already in the SQL analysis are used. No new KPIs were added.

---

## 1. Import the data
1. Open Power BI Desktop → **Home → Get data → Text/CSV**.
2. Import these from `data/processed/powerbi/` (click **Transform Data**, not Load, for the last file so you can set types):
   `dim_accounts.csv`, `dim_users.csv`, `dim_date.csv`, `dim_feature.csv`, `fact_events.csv`.
3. Import these from `data/processed/kpi_tables/`: `q07_new_vs_established.csv`, `q08_engagement_by_plan.csv`,
   `q09_engagement_by_industry.csv`, `q10_inactive_accounts.csv`.
4. In Power Query, for each table set these column types (**Transform → Data Type**):
   * `dim_date`: `date` = Date; `year`, `month_number`, `iso_week`, `iso_weekday` = Whole number
   * `fact_events`: `event_date` = Date; `event_timestamp` = Date/Time
   * `dim_accounts`: `signup_date`, `last_event_date` = Date; `n_users`, `events_90d`, `active_users_90d`,
     `features_used_90d`, `active_days_90d` and all `is_*` columns = Whole number
   * `dim_users`: `created_date` = Date; `created_at` = Date/Time
   * `dim_feature`: `sort_order` = Whole number
   * KPI tables: numeric columns (`*_pct*`, `*_accounts`, `events_per_account_30d`) = Decimal number; `signup_date`, `last_event_date` = Date; the rest Text
5. **Home → Close & Apply**.

## 2. Model (Model view)
Create each relationship by dragging the key from the **one** side onto the **many** side. All are
**Many to one (*:1)**, cross-filter direction **Single**, active.

| One side | Many side |
|---|---|
| `dim_date[date]` | `fact_events[event_date]` |
| `dim_accounts[account_id]` | `fact_events[account_id]` |
| `dim_users[user_id]` | `fact_events[user_id]` |
| `dim_feature[feature_name]` | `fact_events[feature_name]` |

* Do **not** relate `dim_users` to `dim_accounts` (ambiguous path to `fact_events`).
* Leave the four KPI tables (`q07…`, `q08…`, `q09…`, `q10…`) unrelated.
* `dim_date` → **Table tools → Mark as date table** → `date`.
* Sorting columns: select `dim_feature[feature_name]` → **Column tools → Sort by column → `sort_order`**.
  Select `dim_date[year_month]` (sorts correctly as text). For plan and size order, create two calculated columns
  (**Table view → dim_accounts → New column**), then set **Sort by column** on the text column:
  ```
  plan_sort = SWITCH ( dim_accounts[subscription_plan], "Starter", 1, "Professional", 2, "Enterprise", 3 )
  size_sort = SWITCH ( dim_accounts[company_size], "1-10", 1, "11-50", 2, "51-200", 3, "201+", 4 )
  ```
  Sort `dim_accounts[subscription_plan]` by `plan_sort` and `dim_accounts[company_size]` by `size_sort`.
  Do the same for the `segment` column of `q08_engagement_by_plan` (create the same `plan_sort` SWITCH on `[segment]`).

## 3. Measures
1. **Home → Enter data** → create a table named `_Measures` with one blank column; load it. Hide the blank column.
2. Select `_Measures` → **Home → New measure**, and paste each measure from `dashboards/powerbi_measures.dax`
   (one measure per **New measure**; copy from the measure name to the end of its expression, skip `//` comment lines).
   Measures used by this dashboard:

| Page | Measures |
|---|---|
| 1 | `Total Accounts`, `Active Users`, `Active Accounts`, `DAU`, `Avg DAU`, `DAU 7D Avg`, `MAU`, `Latest Month`, `MAU (Latest Month)`, `DAU/MAU Ratio`, `DAU/MAU (Latest Month)`, `Activation Cohort Accounts`, `Activated Accounts`, `Activation Rate` |
| 2 | `Accounts Using Feature`, `Users Using Feature`, `Account Adoption %`, `User Adoption %`, `Total Events`, `Feature Event Share %` |
| 3 | `Inactive Eligible Accounts`, `Inactive Accounts`, `Inactive Account %` |

3. Formats (**Measure tools**): `Activation Rate`, `Account Adoption %`, `User Adoption %`, `Feature Event Share %`,
   `Inactive Account %` → Percentage, 1 decimal. `DAU/MAU Ratio`, `DAU/MAU (Latest Month)` → Decimal, 3 places.
   `Avg DAU`, `DAU 7D Avg` → Decimal, 1 place. Counts → Whole number, thousands separator.

## 4. Build the report
**Setup:** **View → Themes → Browse for themes** → `dashboards/theme.json`. **View → Page view → Actual size**.
**Format page → Canvas settings:** Type *16:9* (1280 × 720). Rename the pages `Product Overview`, `Feature Adoption`,
`Customer Engagement`. For every visual, set size and position in **Format → General → Properties → Size / Position**
using the X, Y, W, H below (pixels). Turn **off** the Filters pane for screenshots (View → Filters). No slicers are used, so every
value stays equal to the SQL result.

**Page header (all pages):** Insert → Text box at X0 Y0 W1280 H56, fill `#1F5FA8`, white 20 pt semibold text.
Page 1: "SaaS CRM Product Usage – Product Overview"; page 2: "… – Feature Adoption"; page 3: "… – Customer Engagement".
Footer text box (X20 Y700 W1240 H20, 9 pt gray): "Synthetic data · observation window 2026-01-01 to 2026-03-31 (90 days)".

### Page 1 – Product Overview
| # | Visual | Chart type | Fields | X Y W H | Notes |
|---|---|---|---|---|---|
| 1.1 | Total Accounts | Card | `Total Accounts` | 20 70 232 100 | |
| 1.2 | Active Users (90 days) | Card | `Active Users` | 272 70 232 100 | title "Active users (90 days)" |
| 1.3 | DAU | Card | `Avg DAU` | 524 70 232 100 | title "Avg DAU (90 days)" |
| 1.4 | MAU | Card | `MAU (Latest Month)` | 776 70 232 100 | title "MAU (March 2026)" |
| 1.5 | Activation Rate | Card | `Activation Rate` | 1028 70 232 100 | title "Activation rate (14-day)" |
| 1.6 | Daily active users | Line chart | X-axis `dim_date[date]` (continuous date, not hierarchy); Y-axis `DAU`, `DAU 7D Avg` | 20 190 740 250 | DAU thin gray line, 7D Avg thick blue |
| 1.7 | MAU by month | Clustered column | X-axis `dim_date[year_month]`; Y-axis `MAU` | 780 190 480 250 | data labels on |
| 1.8 | DAU/MAU by month | Line chart with markers | X-axis `dim_date[year_month]`; Y-axis `DAU/MAU Ratio` | 20 460 370 235 | data labels on, 3 decimals |
| 1.9 | Definitions | Text box | – | 410 460 850 235 | text below |

Text for 1.9: *Active = at least one event. DAU = distinct users per day (average over 90 days, zero-activity days
included). MAU = distinct users per calendar month. DAU/MAU = average DAU in the month ÷ MAU of the month. Activation =
of accounts that signed up in the window with ≥14 observed days, the share with ≥2 users and ≥3 features in their first 14 days (103 of 273).*

### Page 2 – Feature Adoption
| # | Visual | Chart type | Fields | X Y W H | Notes |
|---|---|---|---|---|---|
| 2.1 | Feature adoption rate | Clustered bar | Y-axis `dim_feature[feature_name]`; X-axis `Account Adoption %`, `User Adoption %` | 20 70 620 300 | title "Feature adoption – % of active accounts / % of active users"; data labels on; sort by `Account Adoption %` descending |
| 2.2 | Workflow Automation: new vs established | Clustered column | X-axis `q07_new_vs_established[cohort]`; Y-axis `adoption_pct_of_active_accounts` (**Don't summarize** or Maximum); **Visual-level filter** `feature_name` = *Workflow Automation* | 660 70 600 260 | title "Workflow Automation adoption – 30-day window (% of active accounts)"; data labels 1 decimal |
| 2.3 | Usage by subscription plan | Clustered column | X-axis `dim_feature[feature_name]`; Legend `dim_accounts[subscription_plan]`; Y-axis `Account Adoption %` | 20 390 740 305 | title "Feature adoption by plan (% of active accounts in plan)"; plan colors: Starter gray, Professional light blue, Enterprise dark blue |
| 2.4 | Feature usage | Table | `dim_feature[feature_name]`, `Total Events`, `Feature Event Share %` | 780 390 480 305 | sort by `Total Events` descending; add a Total row off |
| 2.5 | Note | Text box | – | 660 334 600 36 | "New = signed up in window, first 30 days; Established = signed up before window, Jan 1–30 (SQL q07)." |

Visual 2.2 is built from the SQL table because new-vs-established needs a fixed 30-day exposure per account, which the
model's 90-day facts cannot give. It is intentionally unrelated to the model, which is fine because the report has no slicers.

### Page 3 – Customer Engagement
| # | Visual | Chart type | Fields | X Y W H | Notes |
|---|---|---|---|---|---|
| 3.1 | Inactive accounts | Card | `Inactive Accounts` | 20 70 200 100 | title "Inactive accounts" |
| 3.2 | Inactive share | Card | `Inactive Account %` | 240 70 200 100 | title "% of eligible accounts" |
| 3.3 | Starter vs Enterprise inactivity | Clustered column | X-axis `dim_accounts[subscription_plan]`; Y-axis `Inactive Account %` | 460 70 390 300 | title "Inactive accounts by plan"; data labels; Starter dark orange (`#E07B39`), others blue |
| 3.4 | Inactivity by company size | Clustered column | X-axis `dim_accounts[company_size]`; Y-axis `Inactive Account %` | 870 70 390 300 | data labels |
| 3.5 | Engagement by plan | Clustered bar | Y-axis `q08_engagement_by_plan[segment]`; X-axis `events_per_account_30d` (Don't summarize / Max) | 20 190 420 180 | title "Events per account per 30 days" |
| 3.6 | Engagement by industry | Clustered bar | Y-axis `q09_engagement_by_industry[segment]`; X-axis `events_per_account_30d` (Don't summarize / Max) | 20 390 620 305 | sort ascending so the lowest-engagement industry is on top; data labels |
| 3.7 | Inactive accounts list | Table | `q10_inactive_accounts`: `account_id`, `subscription_plan`, `company_size`, `industry`, `inactivity_type`, `last_event_date`, `latest_subscription_status` | 660 390 600 305 | sort by `last_event_date` ascending; 285 rows |

Cards 3.1/3.2 and charts 3.3/3.4 use the model (`dim_accounts` flags `is_inactive_eligible`, `is_inactive_last30d`).
Visuals 3.5–3.7 use the SQL tables so they match q08/q09/q10 exactly. Definition for the page footer:
*Inactive = signed up ≥30 days before 2026-03-31 and no events in the last 30 days (2026-03-02 to 2026-03-31).*

## 5. Validate against SQL
Open `dashboards/expected_values.csv` (or run `python scripts/validate_dashboard.py` to regenerate it). With no filters
applied, each visual must match the `sql_value` column. The ones to check first:

| Visual | Expected |
|---|---|
| 1.1 Total Accounts | 1,200 |
| 1.2 Active Users | 3,575 |
| 1.3 Avg DAU | 169.0 |
| 1.4 MAU (March) | 2,470 |
| 1.5 Activation Rate | 37.7% |
| 1.7 MAU by month | 1,849 / 2,062 / 2,470 |
| 1.8 DAU/MAU by month | 0.075 / 0.083 / 0.080 |
| 2.1 Account adoption | Contact 93.4 · Lead 89.8 · Deal 78.0 · Email 55.4 · Reporting 44.8 · Workflow 26.8 (%) |
| 2.1 User adoption | Contact 82.4 · Lead 78.0 · Deal 67.4 · Email 46.2 · Reporting 35.0 · Workflow 18.8 (%) |
| 2.2 Workflow Automation | New 8.0% · Established 25.9% |
| 2.3 Workflow Automation by plan | Starter 6.8% · Professional 31.6% · Enterprise 60.1% |
| 3.1 / 3.2 | 285 accounts · 26.3% |
| 3.3 Inactive by plan | Starter 36.1% · Professional 20.0% · Enterprise 13.1% |
| 3.4 Inactive by size | 1-10: 41.5% · 11-50: 20.1% · 51-200: 13.9% · 201+: 9.2% |
| 3.5 Events/account/30d by plan | Starter 12.43 · Professional 25.09 · Enterprise 52.84 |

Troubleshooting: if a model-based number is off, check (1) column types from Section 1, (2) the four relationships and
single direction, (3) that no slicer or page filter is active, (4) that `dim_date` is marked as the date table. DAU shown
over a date axis is per day; a card using `DAU` alone would show distinct users for the whole period, so cards use `Avg DAU`.

## 6. Export screenshots for the GitHub README
1. Hide the Filters pane (View → Filters) and set **View → Page view → Actual size**; make sure no visual is selected and
   no tooltip is showing (click empty canvas).
2. **Best quality – export to PDF, then PNG:** **File → Export → Export to PDF** (all pages). Convert each page to PNG at
   150–200 dpi:
   * macOS/Linux: `pdftoppm -r 150 -png dashboard.pdf dashboard` (Poppler) or open in Preview → File → Export → PNG.
   * Windows: open in Edge/Acrobat and snip, or use any PDF-to-PNG tool.
3. **Quick alternative:** a window screenshot with **Win + Shift + S** (Snipping Tool, Rectangle) of one page at 100% zoom on a
   1920×1080 display. Don't resize the image afterwards beyond 1600 px wide.
4. Save as `docs/images/01_product_overview.png`, `02_feature_adoption.png`, `03_customer_engagement.png` in the repo
   (16:9, under ~500 KB each; compress with a tool like TinyPNG if larger).
5. Embed in `README.md` under "Dashboard Overview":
   ```markdown
   ![Product Overview](docs/images/01_product_overview.png)
   ![Feature Adoption](docs/images/02_feature_adoption.png)
   ![Customer Engagement](docs/images/03_customer_engagement.png)
   ```
6. Check each screenshot before committing: values match `expected_values.csv`, the "Synthetic data" footer is visible,
   and no personal information (file paths, account names, Power BI workspace names) appears.
7. Optionally commit the `.pbix` too (File → Save As). It embeds the data (~15 MB); the data is synthetic, so there is no privacy issue.
   Avoid **Publish to web** unless you want a public link.

Do not claim in the README that the DAX was tested in Power BI until you have completed Section 5 yourself.
