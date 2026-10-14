#!/usr/bin/env python3
"""Validate the Streamlit dashboard. Run from the project root:  python dashboards/streamlit/validate_app.py

A. Default filters: dashboard metric functions vs the validated SQL result tables (data/processed/kpi_tables).
B. Filtered scopes: dashboard metrics vs fresh SQL queries run on SQLite with the same filters.
C. Segment filters vs the matching rows of the SQL result tables.
D. Date range: January only vs SQL q01/q02/q03.
E. Headless app run (streamlit.testing AppTest): all three pages, filter changes, edge cases.
Exit code is non-zero on any failure. This does not test visual layout in a real browser.
"""
import csv
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crm_dash import data, metrics as m  # noqa: E402

ROOT = data.ROOT
KPI = data.KPI_DIR
APP = HERE / "app.py"
fails, n_checks = [], 0

# Reference values supplied with the task (checked here, never used by the app).
REFERENCE = {"total_accounts": 1200, "total_users": 6331, "active_users": 3575, "avg_dau": 169.0, "mau": 2470,
             "activation_rate": 37.7, "wa_new": 8.0, "wa_established": 25.9, "starter_inactive": 36.1,
             "enterprise_inactive": 13.1}


def check(label, got, want, tol=0.0):
    global n_checks
    n_checks += 1
    try:
        ok = abs(float(got) - float(want)) <= tol + 1e-9
    except (TypeError, ValueError):
        ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: dashboard={got} reference={want}")
    if not ok:
        fails.append(label)


def truth(label, cond):
    global n_checks
    n_checks += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


def kpi(name):
    with open(KPI / f"{name}.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


ds = data.load_dataset()
ALL = (tuple(ds.accounts.subscription_plan.unique()), tuple(ds.accounts.industry.unique()),
       tuple(ds.accounts.company_size.unique()))


def scope(plans=None, inds=None, sizes=None, start=None, end=None):
    return m.build_scope(ds, m.Filters(tuple(plans or ALL[0]), tuple(inds or ALL[1]), tuple(sizes or ALL[2]),
                                       pd.Timestamp(start or ds.d0), pd.Timestamp(end or ds.d1)))


# ---------------------------------------------------------------- A. defaults vs SQL tables
print("== A. Default filters vs SQL result tables")
s = scope()
k = m.overview_kpis(s)
q00 = kpi("q00_overview")[0]
check("Total accounts (q00)", k["total_accounts"], q00["total_accounts"])
check("Total users (q00)", k["total_users"], q00["total_users"])
check("Active users (q00)", k["active_users"], q00["active_users_90d"])
check("Active accounts (q00)", k["active_accounts"], q00["active_accounts_90d"])
check("Average DAU (q00)", round(k["avg_dau"], 1), q00["avg_dau"])
check("MAU latest month (q00)", k["mau"], q00["mau_latest_month"])
act = m.activation_summary(m.activation_accounts(s)).iloc[0]
check("Activation cohort (q00)", act.cohort_accounts, q00["activation_cohort_accounts"])
check("Activated accounts (q00)", act.activated_accounts, q00["activated_accounts"])
check("Activation rate % (q00)", round(act.activation_rate_pct, 1), q00["activation_rate_pct"])
mo = m.monthly_series(s).set_index("month")
for r in kpi("q03_dau_mau_ratio"):
    check(f"MAU {r['month']} (q03)", mo.loc[r["month"], "mau"], kpi("q02_mau")[[x["month"] for x in kpi("q02_mau")].index(r["month"])]["mau"])
    check(f"DAU/MAU {r['month']} (q03)", round(mo.loc[r["month"], "dau_mau_ratio"], 4), r["dau_mau_ratio"], 0.00006)
ds_q01 = kpi("q01_dau")
dd = m.daily_series(s)
truth("DAU series: 90 days, values equal q01", len(dd) == 90 and all(int(a["dau"]) == int(b) for a, b in zip(ds_q01, dd.dau)))
truth("DAU 7-day average equals q01", all(abs(float(a["dau_7d_avg"]) - b) < 0.051 for a, b in zip(ds_q01, dd.dau_7d_avg)))
for r in kpi("q04_activation_rate"):
    if r["dimension"] == "Plan":
        row = m.activation_summary(m.activation_accounts(s), "subscription_plan").set_index("segment").loc[r["segment"]]
        check(f"Activation {r['segment']} (q04)", round(row.activation_rate_pct, 1), r["activation_rate_pct"])
fa = m.feature_adoption(s).set_index("feature_name")
for r in kpi("q05_feature_adoption"):
    check(f"Account adoption {r['feature_name']} (q05)", round(fa.loc[r["feature_name"], "account_adoption_pct"], 1),
          r["account_adoption_pct_of_active_accounts"])
    check(f"User adoption {r['feature_name']} (q05)", round(fa.loc[r["feature_name"], "user_adoption_pct"], 1),
          r["user_adoption_pct_of_active_users"])
for r in kpi("q06_feature_usage_frequency"):
    check(f"Events {r['feature_name']} (q06)", fa.loc[r["feature_name"], "events"], r["events"])
    check(f"Events/using user {r['feature_name']} (q06)", round(fa.loc[r["feature_name"], "events_per_using_user"], 1),
          r["events_per_using_user"])
nv = m.new_vs_established(s).set_index(["cohort", "feature_name"])
for r in kpi("q07_new_vs_established"):
    check(f"{r['feature_name']} | {r['cohort'][:11]} (q07)", round(nv.loc[(r["cohort"], r["feature_name"]), "adoption_pct"], 1),
          r["adoption_pct_of_active_accounts"])
bp = m.feature_by_plan(s).set_index(["subscription_plan", "feature_name"])
for r in kpi("q08b_feature_by_plan"):
    check(f"{r['plan']} | {r['feature_name']} adoption (q08b)", round(bp.loc[(r["plan"], r["feature_name"]), "adoption_pct"], 1),
          r["adoption_pct_of_active_accounts"])
    check(f"{r['plan']} | {r['feature_name']} event mix (q08b)", round(bp.loc[(r["plan"], r["feature_name"]), "pct_of_plan_events"], 1),
          r["pct_of_plan_events"])
for q, by in (("q08_engagement_by_plan", "subscription_plan"), ("q09_engagement_by_industry", "industry"),
              ("q09b_engagement_by_company_size", "company_size")):
    seg = m.segment_engagement(s, by).set_index("segment")
    for r in kpi(q):
        for col, qcol, tol in (("accounts", "accounts", 0), ("active_accounts", "active_accounts", 0),
                               ("total_users", "total_users", 0), ("active_users", "active_users", 0),
                               ("events", "events", 0), ("pct_accounts_active", "pct_accounts_active", 0.051),
                               ("pct_users_active", "pct_users_active", 0.051),
                               ("events_per_account_30d", "events_per_account_30d", 0.0051),
                               ("events_per_active_user", "events_per_active_user", 0.051)):
            check(f"{q} {r['segment']} {col}", seg.loc[r["segment"], col], r[qcol], tol)
inact = m.inactive_accounts(s)
truth("Inactive list length equals q10", int(inact.inactive.sum()) == len(kpi("q10_inactive_accounts")))
truth("Inactive account IDs equal q10",
      set(inact[inact.inactive].account_id) == {r["account_id"] for r in kpi("q10_inactive_accounts")})
for r in kpi("q10b_inactive_summary"):
    by = {"All": None, "Plan": "subscription_plan", "Company size": "company_size", "Industry": "industry"}[r["dimension"]]
    sm = m.inactive_summary(inact, by)
    row = sm.iloc[0] if by is None else sm.set_index("segment").loc[r["segment"]]
    check(f"Inactive {r['dimension']}/{r['segment']} eligible (q10b)", row.eligible_accounts, r["eligible_accounts"])
    check(f"Inactive {r['dimension']}/{r['segment']} inactive (q10b)", row.inactive_accounts, r["inactive_accounts"])
    check(f"Inactive {r['dimension']}/{r['segment']} never active (q10b)", row.never_active_accounts, r["never_active_accounts"])
    check(f"Inactive {r['dimension']}/{r['segment']} % (q10b)", round(row.inactive_pct, 1), r["inactive_pct_of_eligible"])

print("\n-- Task reference values (supplied by the user; compared, not hardcoded in the app)")
check("Ref total accounts", k["total_accounts"], REFERENCE["total_accounts"])
check("Ref total users", k["total_users"], REFERENCE["total_users"])
check("Ref active users", k["active_users"], REFERENCE["active_users"])
check("Ref average DAU", round(k["avg_dau"], 1), REFERENCE["avg_dau"])
check("Ref March MAU", k["mau"], REFERENCE["mau"])
check("Ref activation rate", round(act.activation_rate_pct, 1), REFERENCE["activation_rate"])
check("Ref activation numerator/denominator", f"{act.activated_accounts}/{act.cohort_accounts}", "103/273")
check("Ref WA new accounts", round(nv.loc[("New (signed up in window)", "Workflow Automation"), "adoption_pct"], 1), REFERENCE["wa_new"])
check("Ref WA established", round(nv.loc[("Established (signed up before window)", "Workflow Automation"), "adoption_pct"], 1), REFERENCE["wa_established"])
ib = m.inactive_summary(inact, "subscription_plan").set_index("segment")
check("Ref Starter inactivity", round(ib.loc["Starter", "inactive_pct"], 1), REFERENCE["starter_inactive"])
check("Ref Enterprise inactivity", round(ib.loc["Enterprise", "inactive_pct"], 1), REFERENCE["enterprise_inactive"])

# ---------------------------------------------------------------- B. filtered scopes vs fresh SQL
print("\n== B. Filtered scopes vs direct SQL on SQLite")
con = sqlite3.connect(data.DB_PATH)


def sql_scalar(sql, params):
    return con.execute(sql, params).fetchone()[0]


CASES = [
    dict(plans=["Starter"]),
    dict(plans=["Professional", "Enterprise"], inds=["Technology", "Healthcare"]),
    dict(plans=["Starter"], inds=["Manufacturing"], sizes=["1-10", "11-50"], start="2026-02-01", end="2026-03-15"),
    dict(sizes=["201+"], start="2026-01-15", end="2026-02-14"),
]
for case in CASES:
    sc = scope(case.get("plans"), case.get("inds"), case.get("sizes"), case.get("start"), case.get("end"))
    f = sc.f
    start, end = f.start.strftime("%Y-%m-%d"), f.end.strftime("%Y-%m-%d")
    inl = lambda col, vals: f"{col} IN ({','.join('?' * len(vals))})"  # noqa: E731
    cond = " AND ".join([inl("a.subscription_plan", f.plans), inl("a.industry", f.industries), inl("a.company_size", f.sizes)])
    p = list(f.plans) + list(f.industries) + list(f.sizes)
    tag = str({k_: v for k_, v in case.items()})
    kk = m.overview_kpis(sc)
    ev_sql = f"FROM events e JOIN accounts a USING(account_id) WHERE {cond} AND date(e.event_timestamp) BETWEEN ? AND ?"
    check(f"{tag} active users", kk["active_users"], sql_scalar(f"SELECT COUNT(DISTINCT e.user_id) {ev_sql}", p + [start, end]))
    check(f"{tag} active accounts", kk["active_accounts"], sql_scalar(f"SELECT COUNT(DISTINCT e.account_id) {ev_sql}", p + [start, end]))
    check(f"{tag} total accounts", kk["total_accounts"],
          sql_scalar(f"SELECT COUNT(*) FROM accounts a WHERE {cond} AND a.signup_date <= ?", p + [end]))
    check(f"{tag} total users", kk["total_users"], sql_scalar(
        f"SELECT COUNT(*) FROM users u JOIN accounts a USING(account_id) WHERE {cond} AND date(u.created_at) <= ?", p + [end]))
    n_days = (f.end - f.start).days + 1
    daily_sum = sql_scalar(f"SELECT SUM(c) FROM (SELECT COUNT(DISTINCT e.user_id) c {ev_sql} GROUP BY date(e.event_timestamp))", p + [start, end])
    check(f"{tag} average DAU", round(kk["avg_dau"], 4), round((daily_sum or 0) / n_days, 4), 0.00006)
    last_m0 = max(f.start, f.end.replace(day=1)).strftime("%Y-%m-%d")
    mau_sql = sql_scalar(f"SELECT COUNT(DISTINCT e.user_id) {ev_sql}", p + [last_m0, end])
    check(f"{tag} MAU (last month in range)", kk["mau"], mau_sql)
    check(f"{tag} events in range", len(sc.events), sql_scalar(f"SELECT COUNT(*) {ev_sql}", p + [start, end]))
    # inactive (fixed) with filters
    cut = (ds.d1 - pd.Timedelta(days=29)).strftime("%Y-%m-%d")
    sql_inact = sql_scalar(
        f"SELECT COUNT(*) FROM accounts a WHERE {cond} AND a.signup_date <= ? AND NOT EXISTS "
        "(SELECT 1 FROM events e WHERE e.account_id = a.account_id AND date(e.event_timestamp) >= ?)", p + [cut, cut])
    check(f"{tag} inactive accounts (fixed definition)", int(m.inactive_accounts(sc).inactive.sum()), sql_inact)
    # activation (fixed) with filters
    sql_act = sql_scalar(
        f"""SELECT SUM(x.ok) FROM (SELECT CASE WHEN COUNT(DISTINCT e.user_id) >= 2 AND COUNT(DISTINCT e.feature_name) >= 3
            THEN 1 ELSE 0 END AS ok FROM accounts a LEFT JOIN events e ON e.account_id = a.account_id
            AND date(e.event_timestamp) >= a.signup_date AND date(e.event_timestamp) < date(a.signup_date, '+14 days')
            WHERE {cond} AND a.signup_date BETWEEN '2026-01-01' AND '2026-03-18' GROUP BY a.account_id) x""", p)
    ac = m.activation_accounts(sc)
    check(f"{tag} activated accounts (fixed definition)", int(ac.activated.sum()), sql_act or 0)

# ---------------------------------------------------------------- C. segment filter vs SQL table rows
print("\n== C. Single-segment filters reproduce the SQL segment rows")
q08 = {r["segment"]: r for r in kpi("q08_engagement_by_plan")}
for plan in data.PLAN_ORDER:
    sc = scope(plans=[plan])
    kk = m.overview_kpis(sc)
    check(f"{plan}: accounts = q08", kk["total_accounts"], q08[plan]["accounts"])
    check(f"{plan}: active accounts = q08", kk["active_accounts"], q08[plan]["active_accounts"])
    check(f"{plan}: active users = q08", kk["active_users"], q08[plan]["active_users"])
    check(f"{plan}: activation = q04", round(m.activation_summary(m.activation_accounts(sc)).iloc[0].activation_rate_pct, 1),
          [r for r in kpi("q04_activation_rate") if r["dimension"] == "Plan" and r["segment"] == plan][0]["activation_rate_pct"])
q09 = {r["segment"]: r for r in kpi("q09_engagement_by_industry")}
for ind, r in q09.items():
    sc = scope(inds=[ind])
    check(f"{ind}: events/account/30d = q09", round(m.segment_engagement(sc, "industry").iloc[0].events_per_account_30d, 2), r["events_per_account_30d"])
q09b = {r["segment"]: r for r in kpi("q09b_engagement_by_company_size")}
for size, r in q09b.items():
    sc = scope(sizes=[size])
    check(f"{size}: active accounts = q09b", m.overview_kpis(sc)["active_accounts"], r["active_accounts"])
# segment partition sums
for by, col in (("subscription_plan", "plans"), ("industry", "inds"), ("company_size", "sizes")):
    tot = sum(m.overview_kpis(scope(**{col: [v]}))["active_users"] for v in ds.accounts[by].unique())
    check(f"Active users partition sum over {by} = total", tot, k["active_users"])

# ---------------------------------------------------------------- D. date range
print("\n== D. Date range vs SQL q01/q02/q03 (January only)")
jan = scope(start="2026-01-01", end="2026-01-31")
kj = m.overview_kpis(jan)
q01 = kpi("q01_dau")
check("Jan average DAU = mean of q01 January DAU", round(kj["avg_dau"], 3), round(sum(int(r["dau"]) for r in q01[:31]) / 31, 3), 0.0011)
check("Jan MAU = q02", kj["mau"], [r for r in kpi("q02_mau") if r["month"] == "2026-01"][0]["mau"])
check("Jan DAU/MAU = q03", round(kj["dau_mau_ratio"], 4), [r for r in kpi("q03_dau_mau_ratio") if r["month"] == "2026-01"][0]["dau_mau_ratio"], 0.00006)
truth("Partial month is flagged", m.overview_kpis(scope(start="2026-03-10", end="2026-03-20"))["mau_partial"] is True)
truth("Full month is not flagged", kj["mau_partial"] is False)
check("Fixed-definition activation ignores date range", m.activation_summary(m.activation_accounts(jan)).iloc[0].activated_accounts, 103)
check("Fixed-definition inactivity ignores date range", int(m.inactive_accounts(jan).inactive.sum()), 285)
check("7-day average inside range uses earlier days (Jan 3 = q01)", round(m.daily_series(scope(start="2026-01-03", end="2026-01-10")).dau_7d_avg.iloc[0], 1),
      q01[2]["dau_7d_avg"], 0.051)

# ---------------------------------------------------------------- E. headless app run
print("\n== E. Headless app run (streamlit.testing AppTest)")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["views/product_overview.py", "views/feature_adoption.py", "views/customer_engagement.py"]
EXPECTED_CHARTS = {PAGES[0]: 4, PAGES[1]: 5, PAGES[2]: 5}


def cards(at):
    out = {}
    for md in at.markdown:
        for lab, val in re.findall(r'class="label">(.*?)</div><div class="value">(.*?)</div>', md.value):
            out[lab.replace("&amp;", "&")] = val
    return out


def run_pages(at, tag, expect_charts=True):
    for pg in PAGES:
        at.switch_page(pg).run()
        truth(f"{tag}: {pg} has no exceptions", not at.exception)
        if expect_charts:
            truth(f"{tag}: {pg} renders {EXPECTED_CHARTS[pg]} charts (found {len(at.get('plotly_chart'))})",
                  len(at.get("plotly_chart")) == EXPECTED_CHARTS[pg])
    at.switch_page(PAGES[0]).run()


at = AppTest.from_file(str(APP), default_timeout=90).run()
truth("App starts without exception", not at.exception)
c = cards(at)
check("UI card Total CRM accounts", c["Total CRM accounts"].replace(",", ""), k["total_accounts"])
check("UI card Total users", c["Total users"].replace(",", ""), k["total_users"])
check("UI card Active users", c["Active users"].replace(",", ""), k["active_users"])
check("UI card Average DAU", c["Average DAU"], f"{k['avg_dau']:.1f}")
check("UI card MAU", c["MAU (2026-03)"].replace(",", ""), k["mau"])
check("UI card Activation", c["Account activation rate"], f"{round(act.activation_rate_pct, 1)}%")
check("UI card DAU/MAU", c["DAU / MAU ratio"], f"{k['dau_mau_ratio']:.3f}")
run_pages(at, "default filters")

at.multiselect(key="f_plans").set_value(["Starter"]).run()
c = cards(at)
check("UI after Plan=Starter: Total accounts", c["Total CRM accounts"].replace(",", ""), q08["Starter"]["accounts"])
check("UI after Plan=Starter: Active users", c["Active users"].replace(",", ""), q08["Starter"]["active_users"])
run_pages(at, "Plan=Starter")
at.switch_page(PAGES[2]).run()
c = cards(at)
check("UI Customer Engagement: Starter inactivity", c["Starter inactivity rate"], f"{ib.loc['Starter', 'inactive_pct']:.1f}%")
truth("UI Customer Engagement: Enterprise inactivity shows n/a when plan filtered out", c["Enterprise inactivity rate"] == "n/a")

at.multiselect(key="f_plans").set_value(["Starter", "Professional", "Enterprise"])
at.multiselect(key="f_industries").set_value(["Technology"])
at.multiselect(key="f_sizes").set_value(["11-50", "51-200"])
at.date_input(key="f_dates").set_value((date(2026, 2, 1), date(2026, 2, 28))).run()
truth("Combined plan+industry+size+date filter: no exception", not at.exception)
sc = scope(inds=["Technology"], sizes=["11-50", "51-200"], start="2026-02-01", end="2026-02-28")
at.switch_page(PAGES[0]).run()
check("UI combined filters: Active users", cards(at)["Active users"].replace(",", ""), m.overview_kpis(sc)["active_users"])
run_pages(at, "combined filters")

at.multiselect(key="f_plans").set_value([]).run()
truth("Empty filter selection shows a warning (no crash)", bool(at.warning) and not at.exception)
at.multiselect(key="f_plans").set_value(["Starter", "Professional", "Enterprise"])
at.multiselect(key="f_industries").set_value(["Technology", "Healthcare", "Education", "Manufacturing", "Financial Services",
                                              "Real Estate", "Retail & E-commerce", "Professional Services"])
at.multiselect(key="f_sizes").set_value(["1-10", "11-50", "51-200", "201+"])
at.date_input(key="f_dates").set_value((date(2026, 1, 1), date(2026, 3, 31))).run()
truth("Filters restored to defaults: no exception", not at.exception)
at.switch_page(PAGES[0]).run()
check("UI restored: Active users", cards(at)["Active users"].replace(",", ""), k["active_users"])

print(f"\n{n_checks} checks run")
if fails:
    print(f"{len(fails)} FAILED:")
    for f_ in fails:
        print("  -", f_)
    sys.exit(1)
print("ALL DASHBOARD VALIDATION CHECKS PASSED")
