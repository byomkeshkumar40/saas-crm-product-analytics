"""Page 2 - Feature Adoption."""
import pandas as pd
import streamlit as st

from crm_dash import charts, metrics, ui
from crm_dash.data import FEATURES

scope = st.session_state.get("scope")
if scope is None:
    st.warning("Open the dashboard through app.py (streamlit run dashboards/streamlit/app.py).")
    st.stop()

f = scope.f
fa = metrics.feature_adoption(scope)
nv = metrics.new_vs_established(scope)
byplan = metrics.feature_by_plan(scope)
wa = fa[fa.feature_name == "Workflow Automation"].iloc[0]

ui.header("Feature Adoption", "Which CRM features accounts and users adopt, and where automation lags")
ui.scope_note(f"<b>Date range:</b> {f.start:%b %d} to {f.end:%b %d, %Y} applies to feature adoption rates, usage frequency and "
              "usage by plan. <b>New vs established</b> uses a fixed 30-day exposure per account and ignores the date range. "
              "Plan / industry / size filters apply everywhere.")


def nv_cell(cohort_prefix):
    r = nv[(nv.cohort.str.startswith(cohort_prefix)) & (nv.feature_name == "Workflow Automation")]
    if r.empty:
        return "n/a", "No eligible accounts for these filters"
    r = r.iloc[0]
    return ui.fmt_pct(r.adoption_pct), f"{int(r.adopting_accounts)} of {int(r.active_accounts)} active accounts · 30-day exposure"


new_v, new_n = nv_cell("New")
est_v, est_n = nv_cell("Established")
ui.kpi_row([
    ("Workflow Automation · account adoption", ui.fmt_pct(wa.account_adoption_pct),
     f"{wa.accounts_using} of {wa.active_accounts} active accounts in selected range"),
    ("Workflow Automation · user adoption", ui.fmt_pct(wa.user_adoption_pct),
     f"{wa.users_using} of {wa.active_users} active users in selected range"),
    ("New accounts · Workflow Automation", new_v, new_n),
    ("Established accounts · Workflow Automation", est_v, est_n),
], accent=True)

left, right = st.columns(2)
with left:
    ui.section("Feature adoption rate", "Account level = ÷ active accounts; user level = ÷ active users (selected range)")
    ui.plot(charts.feature_adoption_bar(fa), key="fa")
with right:
    ui.section("Feature usage frequency", "Events per feature (selected range); label = share of all events")
    ui.plot(charts.usage_frequency(fa), key="uf")

ui.section("New vs established accounts",
           "% of active accounts using each feature in a fixed 30-day exposure. New: first 30 days after signup "
           "(signed up Jan 1 – Mar 2). Established: Jan 1 – Jan 30.")
if nv.empty:
    st.info("No accounts qualify for the new-vs-established comparison with these filters.")
else:
    ui.plot(charts.new_vs_est(nv), key="nv")

left, right = st.columns(2)
with left:
    ui.section("Feature adoption by subscription plan", "% of active accounts in the plan using each feature (selected range)")
    ui.plot(charts.adoption_by_plan(byplan), key="bp")
with right:
    ui.section("Feature mix by subscription plan", "Share of each plan's events by feature (selected range)")
    ui.plot(charts.event_mix_by_plan(byplan), key="mix")

with st.expander("Data tables"):
    t = fa[["feature_name", "accounts_using", "active_accounts", "account_adoption_pct", "users_using",
            "active_users", "user_adoption_pct", "events", "pct_of_all_events", "events_per_using_user"]].round(1)
    st.dataframe(t, hide_index=True, **ui.STRETCH)
    st.dataframe(nv.round(1), hide_index=True, **ui.STRETCH)
ui.footer()
