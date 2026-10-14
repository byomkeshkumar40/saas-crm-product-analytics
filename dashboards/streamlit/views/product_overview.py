"""Page 1 - Product Overview."""
import streamlit as st

from crm_dash import charts, metrics, ui

scope = st.session_state.get("scope")
if scope is None:
    st.warning("Open the dashboard through app.py (streamlit run dashboards/streamlit/app.py).")
    st.stop()

f = scope.f
k = metrics.overview_kpis(scope)
act = metrics.activation_accounts(scope)
act_all = metrics.activation_summary(act).iloc[0]
daily = metrics.daily_series(scope)
monthly = metrics.monthly_series(scope)

ui.header("Product Overview", "Reach, activity and activation across the filtered CRM accounts")
rng = f"{f.start:%b %d, %Y} to {f.end:%b %d, %Y}"
ui.scope_note(f"<b>Date range:</b> {rng} ({k['days']} days). Plan / industry / size filters apply to every number. "
              "<b>Activation rate</b> is a fixed 14-day cohort metric and ignores the date range.")

mau_note = f"Users with ≥1 event in {k['mau_month']}" + (" (month only partly in range)" if k["mau_partial"] else "")
ui.kpi_row([
    ("Total CRM accounts", ui.fmt_int(k["total_accounts"]), f"Signed up on or before {f.end:%b %d}"),
    ("Total users", ui.fmt_int(k["total_users"]), f"Created on or before {f.end:%b %d}"),
    ("Active users", ui.fmt_int(k["active_users"]),
     f"≥1 event in range · {ui.fmt_pct(metrics.pct(k['active_users'], k['total_users']))} of total users"),
    ("Active accounts", ui.fmt_int(k["active_accounts"]),
     f"≥1 event in range · {ui.fmt_pct(metrics.pct(k['active_accounts'], k['total_accounts']))} of accounts"),
], accent=True)
st.write("")
if act_all.cohort_accounts:
    act_val = ui.fmt_pct(act_all.activation_rate_pct)
    act_note = (f"{int(act_all.activated_accounts)}/{int(act_all.cohort_accounts)} cohort accounts · ≥2 users and ≥3 "
                "features in first 14 days · date range not applied")
else:
    act_val, act_note = "n/a", "No accounts in the activation cohort for these filters"
ui.kpi_row([
    ("Average DAU", ui.fmt_num(k["avg_dau"]), f"Mean daily active users over {k['days']} days, zero days included"),
    (f"MAU ({k['mau_month']})", ui.fmt_int(k["mau"]), mau_note),
    ("DAU / MAU ratio", f"{k['dau_mau_ratio']:.3f}" if k["dau_mau_ratio"] == k["dau_mau_ratio"] else "n/a",
     f"Avg DAU in {k['mau_month']} ÷ MAU of {k['mau_month']}"),
    ("Account activation rate", act_val, act_note),
], accent=True)

left, right = st.columns([2, 1])
with left:
    ui.section("Daily active users", "Distinct users with ≥1 event per day; the line is a trailing 7-day average")
    ui.plot(charts.dau_trend(daily), key="dau")
with right:
    ui.section("Monthly active users", "Distinct users per calendar month (lighter bar = partial month)")
    ui.plot(charts.mau_bars(monthly), key="mau")

left, right = st.columns(2)
with left:
    ui.section("Activation rate by subscription plan",
               "Accounts that signed up Jan 1 – Mar 18 · activated = ≥2 users and ≥3 features in first 14 days")
    by_plan = metrics.activation_summary(act, "subscription_plan")
    if by_plan.empty:
        st.info("No activation-cohort accounts for the selected filters.")
    else:
        ui.plot(charts.activation_by_plan(by_plan), key="act")
with right:
    ui.section("User engagement overview",
               "Users by plan: active (≥1 event in range) vs not active; label = % of users active")
    ui.plot(charts.user_engagement(metrics.users_by_plan(scope)), key="eng")

with st.expander("Metric definitions and filter scope"):
    st.markdown("""
| Metric | Definition | Plan / industry / size | Date range |
|---|---|---|---|
| Total accounts / users | Accounts signed up / users created on or before the range end | Applied | Range end only |
| Active users, active accounts | Distinct users / accounts with ≥1 event in range | Applied | Applied |
| Average DAU | Mean of daily distinct active users over every day in range (zero days count) | Applied | Applied |
| MAU, DAU/MAU | Last calendar month in range: distinct users; avg DAU ÷ MAU (partial months flagged) | Applied | Applied |
| Activation rate | Accounts signed up in window with ≥14 observed days: share with ≥2 users and ≥3 features in first 14 days | Applied | **Not applied** (fixed cohort) |
""")
ui.footer()
