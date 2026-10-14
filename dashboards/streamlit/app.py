"""SaaS CRM Product Analytics - Streamlit dashboard entry point.

Run from the project root:   streamlit run dashboards/streamlit/app.py
Renders the sidebar filters once, builds the filtered scope, then runs the selected page from views/.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crm_dash import data, metrics, ui  # noqa: E402

st.set_page_config(page_title="SaaS CRM Product Analytics", page_icon=":bar_chart:", layout="wide",
                   initial_sidebar_state="expanded")
ui.inject_css()


@st.cache_resource(show_spinner="Loading SQLite database...")
def get_dataset():
    return data.load_dataset()


try:
    ds = get_dataset()
except data.MissingDataError as exc:
    st.error("Required data file is missing.")
    st.code(str(exc))
    st.stop()

ALL_PLANS = [p for p in data.PLAN_ORDER if p in set(ds.accounts.subscription_plan)]
ALL_INDUSTRIES = sorted(ds.accounts.industry.unique())
ALL_SIZES = [s for s in data.SIZE_ORDER if s in set(ds.accounts.company_size)]
D0, D1 = ds.d0.date(), ds.d1.date()


def reset_filters():
    st.session_state["f_plans"] = ALL_PLANS
    st.session_state["f_industries"] = ALL_INDUSTRIES
    st.session_state["f_sizes"] = ALL_SIZES
    st.session_state["f_dates"] = (D0, D1)


with st.sidebar:
    st.markdown("### Filters")
    plans = st.multiselect("Subscription plan", ALL_PLANS, default=ALL_PLANS, key="f_plans")
    industries = st.multiselect("Industry", ALL_INDUSTRIES, default=ALL_INDUSTRIES, key="f_industries")
    sizes = st.multiselect("Company size", ALL_SIZES, default=ALL_SIZES, key="f_sizes")
    dates = st.date_input("Date range", value=(D0, D1), min_value=D0, max_value=D1, key="f_dates")
    st.button("Reset filters", on_click=reset_filters, **ui.STRETCH)
    st.markdown("---")
    st.caption(
        "**What the filters do**\n\n"
        "- Plan / industry / size: every metric.\n"
        "- Date range: DAU, MAU, active users, feature adoption & usage, engagement by segment.\n"
        "- Not affected by date range (fixed definitions): activation rate, new vs established, inactive accounts.")

if not plans or not industries or not sizes:
    st.warning("Select at least one value in every filter.")
    st.stop()
if not isinstance(dates, (tuple, list)) or len(dates) != 2:
    st.info("Select an end date to complete the date range.")
    st.stop()

flt = metrics.Filters(tuple(plans), tuple(industries), tuple(sizes), pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))
scope = metrics.build_scope(ds, flt)
if scope.accounts.empty:
    st.warning("No accounts match the selected filters.")
    st.stop()
st.session_state["scope"] = scope

pages = [
    st.Page("views/product_overview.py", title="Product Overview", icon=":material/dashboard:", default=True),
    st.Page("views/feature_adoption.py", title="Feature Adoption", icon=":material/extension:"),
    st.Page("views/customer_engagement.py", title="Customer Engagement", icon=":material/groups:"),
]
st.navigation(pages).run()
