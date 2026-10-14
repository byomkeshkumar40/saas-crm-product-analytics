"""Page 3 - Customer Engagement."""
import pandas as pd
import streamlit as st

from crm_dash import charts, metrics, ui
from crm_dash.data import PLAN_ORDER, SIZE_ORDER

scope = st.session_state.get("scope")
if scope is None:
    st.warning("Open the dashboard through app.py (streamlit run dashboards/streamlit/app.py).")
    st.stop()

f = scope.f
inactive = metrics.inactive_accounts(scope)
tot = metrics.inactive_summary(inactive).iloc[0] if len(inactive) else None
by_plan = metrics.inactive_summary(inactive, "subscription_plan") if len(inactive) else None
by_size = metrics.inactive_summary(inactive, "company_size") if len(inactive) else None
cut = scope.ds.d1 - pd.Timedelta(days=29)

ui.header("Customer Engagement", "Inactive accounts and engagement by customer segment")
ui.scope_note(f"<b>Inactive accounts</b> use a fixed definition and ignore the date range: eligible accounts signed up on or before "
              f"{cut:%b %d}, inactive = no events from {cut:%b %d} to {scope.ds.d1:%b %d, %Y}. "
              f"<b>Engagement by segment and trends</b> use the selected range ({f.start:%b %d} to {f.end:%b %d}). "
              "Plan / industry / size filters apply everywhere.")


def plan_cell(plan):
    if by_plan is None or plan not in set(by_plan.segment):
        return "n/a", f"No eligible {plan} accounts for these filters"
    r = by_plan[by_plan.segment == plan].iloc[0]
    return ui.fmt_pct(r.inactive_pct), f"{int(r.inactive_accounts)} of {int(r.eligible_accounts)} eligible {plan} accounts"


if tot is None:
    ui.kpi_row([("Inactive accounts", "n/a", "No eligible accounts for these filters")])
else:
    sv, sn = plan_cell("Starter")
    ev, en = plan_cell("Enterprise")
    ui.kpi_row([
        ("Inactive accounts", ui.fmt_int(tot.inactive_accounts),
         f"{int(tot.never_active_accounts)} never active · {int(tot.lapsed_accounts)} lapsed"),
        ("Inactivity rate", ui.fmt_pct(tot.inactive_pct), f"of {int(tot.eligible_accounts)} eligible accounts"),
        ("Starter inactivity rate", sv, sn),
        ("Enterprise inactivity rate", ev, en),
    ], accent=True)

left, right = st.columns(2)
with left:
    ui.section("Inactivity rate by subscription plan", "% of eligible accounts silent in the last 30 days (label = inactive / eligible)")
    if by_plan is not None:
        ui.plot(charts.inactivity_stack(by_plan, PLAN_ORDER, "Subscription plan"), key="ip")
with right:
    ui.section("Inactivity rate by company size", "Same definition, grouped by employee band")
    if by_size is not None:
        ui.plot(charts.inactivity_stack(by_size, SIZE_ORDER, "Company size"), key="isz")

ui.section("Engagement by customer segment", f"Selected range {f.start:%b %d} to {f.end:%b %d}")
METRICS = {"Events per account (per 30 days)": ("events_per_account_30d", False),
           "% of accounts active": ("pct_accounts_active", True),
           "% of users active": ("pct_users_active", True)}
choice = st.radio("Metric", list(METRICS), horizontal=True, label_visibility="collapsed")
col, is_pct = METRICS[choice]
left, right = st.columns(2)
with left:
    st.markdown("**By industry**")
    ui.plot(charts.segment_bar(metrics.segment_engagement(scope, "industry"), col, choice, pct_axis=is_pct), key="ind")
with right:
    st.markdown("**By company size**")
    ui.plot(charts.segment_bar(metrics.segment_engagement(scope, "company_size"), col, choice, SIZE_ORDER, is_pct), key="siz")

left, right = st.columns([3, 2])
with left:
    ui.section("Customer engagement trend", "Events per day and active accounts per day, trailing 7-day averages")
    ui.plot(charts.engagement_trend(metrics.daily_series(scope)), key="trend")
with right:
    ui.section("Inactive accounts", "Accounts matching the filters (download for outreach)")
    if tot is None or not int(tot.inactive_accounts):
        st.info("No inactive accounts for the selected filters.")
    else:
        lst = inactive[inactive.inactive][["account_id", "subscription_plan", "company_size", "industry", "inactivity_type",
                                           "last_event_date", "latest_subscription_status"]].copy()
        lst["last_event_date"] = lst.last_event_date.dt.date
        st.dataframe(lst.sort_values("last_event_date"), hide_index=True, **ui.STRETCH, height=330)
        st.download_button("Download CSV", lst.to_csv(index=False), "inactive_accounts.csv", "text/csv")
ui.footer()
