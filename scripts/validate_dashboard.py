#!/usr/bin/env python3
"""Check that every dashboard visual's value can be reproduced from the Power BI model tables
(data/processed/powerbi/*.csv) and equals the SQL results (data/processed/kpi_tables/*.csv).

The logic mirrors the DAX in dashboards/powerbi_measures.dax (same filters, same denominators) but runs in plain
Python - it validates the model tables and the measure logic, NOT Power BI's DAX engine. Writes
dashboards/expected_values.csv: the numbers each visual should show once you build the report.
Exit code is non-zero on any mismatch.
"""
import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "data" / "processed" / "powerbi"
KPI = ROOT / "data" / "processed" / "kpi_tables"
OUT = ROOT / "dashboards" / "expected_values.csv"
FEATURES = ["Lead Management", "Contact Management", "Deal Pipeline", "Workflow Automation",
            "Reporting", "Email Integration"]
rows_out, failures = [], []


def read(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(n, d):
    return round(100.0 * n / d, 1)


def cmp(page, visual, field, value, sql_val, source, tol=0.0):
    ok = abs(float(value) - float(sql_val)) <= tol + 1e-9
    rows_out.append([page, visual, field, value, sql_val, source, "PASS" if ok else "FAIL"])
    print(f"[{'PASS' if ok else 'FAIL'}] {page} | {visual} | {field}: model={value} sql={sql_val}")
    if not ok:
        failures.append(f"{visual} / {field}")


def main():
    acc = {r["account_id"]: r for r in read(PBI / "dim_accounts.csv")}
    users = read(PBI / "dim_users.csv")
    dates = read(PBI / "dim_date.csv")
    fact = read(PBI / "fact_events.csv")
    ym = {d["date"]: d["year_month"] for d in dates}
    all_dates = [d["date"] for d in dates]

    dau = defaultdict(set)
    mau = defaultdict(set)
    for e in fact:
        dau[e["event_date"]].add(e["user_id"])
        mau[ym[e["event_date"]]].add(e["user_id"])
    active_users = {e["user_id"] for e in fact}
    active_accts = {e["account_id"] for e in fact}
    q00 = read(KPI / "q00_overview.csv")[0]

    # ---------------- Page 1
    P = "P1 Overview"
    avg_dau = sum(len(dau.get(d, ())) for d in all_dates) / len(all_dates)
    latest = max(ym.values())
    days_latest = [d for d in all_dates if ym[d] == latest]
    cmp(P, "Card", "Total Accounts", len(acc), q00["total_accounts"], "q00")
    cmp(P, "Card", "Active Users", len(active_users), q00["active_users_90d"], "q00")
    cmp(P, "Card", "Avg DAU", round(avg_dau, 1), q00["avg_dau"], "q00", 0.051)
    cmp(P, "Card", f"MAU (Latest Month {latest})", len(mau[latest]), q00["mau_latest_month"], "q00")
    act = sum(int(a["is_activated"]) for a in acc.values())
    coh = sum(int(a["is_activation_cohort"]) for a in acc.values())
    cmp(P, "Card", "Activation Rate %", pct(act, coh), q00["activation_rate_pct"], "q00")
    q02 = {r["month"]: r for r in read(KPI / "q02_mau.csv")}
    q03 = {r["month"]: r for r in read(KPI / "q03_dau_mau_ratio.csv")}
    for m in sorted(q02):
        cmp(P, "MAU by month", m, len(mau[m]), q02[m]["mau"], "q02")
        days = [d for d in all_dates if ym[d] == m]
        ratio = sum(len(dau.get(d, ())) for d in days) / len(days) / len(mau[m])
        cmp(P, "DAU/MAU by month", m, round(ratio, 4), q03[m]["dau_mau_ratio"], "q03", 0.00006)
    cmp(P, "Card", "DAU/MAU (Latest Month)",
        round(sum(len(dau.get(d, ())) for d in days_latest) / len(days_latest) / len(mau[latest]), 3),
        round(float(q03[latest]["dau_mau_ratio"]), 3), "q03", 0.0011)
    series = [len(dau.get(d, ())) for d in all_dates]
    for i, r in enumerate(read(KPI / "q01_dau.csv")):
        w = series[max(0, i - 6): i + 1]
        if r["activity_date"] != all_dates[i] or int(r["dau"]) != series[i] or \
                abs(sum(w) / len(w) - float(r["dau_7d_avg"])) > 0.051:
            failures.append(f"DAU trend {r['activity_date']}")
    cmp(P, "DAU trend line", "90 daily points (DAU and DAU 7D Avg)", 90 - sum(f.startswith("DAU trend") for f in failures), 90, "q01")

    # ---------------- Page 2
    P = "P2 Feature Adoption"
    fa, fu, fev = defaultdict(set), defaultdict(set), defaultdict(int)
    for e in fact:
        fa[e["feature_name"]].add(e["account_id"])
        fu[e["feature_name"]].add(e["user_id"])
        fev[e["feature_name"]] += 1
    for r in read(KPI / "q05_feature_adoption.csv"):
        f = r["feature_name"]
        cmp(P, "Adoption bar", f"{f} - Account Adoption %", pct(len(fa[f]), len(active_accts)),
            r["account_adoption_pct_of_active_accounts"], "q05")
        cmp(P, "Adoption bar", f"{f} - User Adoption %", pct(len(fu[f]), len(active_users)),
            r["user_adoption_pct_of_active_users"], "q05")
    for r in read(KPI / "q06_feature_usage_frequency.csv"):
        f = r["feature_name"]
        cmp(P, "Feature table", f"{f} - Total Events", fev[f], r["events"], "q06")
        cmp(P, "Feature table", f"{f} - Feature Event Share %", pct(fev[f], len(fact)), r["pct_of_all_events"], "q06")
    plan_active = defaultdict(set)
    pf = defaultdict(set)
    for e in fact:
        p = acc[e["account_id"]]["subscription_plan"]
        plan_active[p].add(e["account_id"])
        pf[(p, e["feature_name"])].add(e["account_id"])
    for r in read(KPI / "q08b_feature_by_plan.csv"):
        cmp(P, "Usage by plan", f"{r['plan']} / {r['feature_name']} Account Adoption %",
            pct(len(pf[(r['plan'], r['feature_name'])]), len(plan_active[r['plan']])),
            r["adoption_pct_of_active_accounts"], "q08b")
    # new vs established: fixed 30-day exposure, recomputed from dim_accounts + fact
    d0, d1 = date(2026, 1, 1), date(2026, 3, 31)
    exp = {}
    for a in acc.values():
        s = date.fromisoformat(a["signup_date"])
        if s < d0:
            exp[a["account_id"]] = ("Established (signed up before window)", d0)
        elif s <= d1 - timedelta(29):
            exp[a["account_id"]] = ("New (signed up in window)", s)
    used = defaultdict(set)
    seen = defaultdict(set)
    for e in fact:
        x = exp.get(e["account_id"])
        if not x:
            continue
        ed = date.fromisoformat(e["event_date"])
        if x[1] <= ed < x[1] + timedelta(30):
            seen[x[0]].add(e["account_id"])
            used[(x[0], e["feature_name"])].add(e["account_id"])
    for r in read(KPI / "q07_new_vs_established.csv"):
        c, f = r["cohort"], r["feature_name"]
        cmp(P, "New vs established (q07 table)", f"{c} / {f} %", pct(len(used[(c, f)]), len(seen[c])),
            r["adoption_pct_of_active_accounts"], "q07")

    # ---------------- Page 3
    P = "P3 Engagement"
    elig = [a for a in acc.values() if int(a["is_inactive_eligible"])]
    inactive = [a for a in elig if int(a["is_inactive_last30d"])]
    q10b = {(r["dimension"], r["segment"]): r for r in read(KPI / "q10b_inactive_summary.csv")}
    cmp(P, "Card", "Inactive Accounts", len(inactive), q10b[("All", "All eligible accounts")]["inactive_accounts"], "q10b")
    cmp(P, "Card", "Inactive Account %", pct(len(inactive), len(elig)),
        q10b[("All", "All eligible accounts")]["inactive_pct_of_eligible"], "q10b")
    for dim, col in (("Plan", "subscription_plan"), ("Company size", "company_size")):
        for seg in sorted({a[col] for a in acc.values()}):
            e_ = [a for a in elig if a[col] == seg]
            i_ = [a for a in e_ if int(a["is_inactive_last30d"])]
            cmp(P, f"Inactive % by {dim.lower()}", seg, pct(len(i_), len(e_)),
                q10b[(dim, seg)]["inactive_pct_of_eligible"], "q10b")
    cmp(P, "Inactive table (q10)", "row count", len(read(KPI / "q10_inactive_accounts.csv")), len(inactive), "q10")
    q09 = {r["segment"]: r for r in read(KPI / "q09_engagement_by_industry.csv")}
    for ind, r in q09.items():
        n = [a for a in acc.values() if a["industry"] == ind]
        cmp(P, "Industry engagement (q09)", f"{ind} - accounts active %",
            pct(sum(int(a["is_active_90d"]) for a in n), len(n)), r["pct_accounts_active"], "q09")

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "visual", "field", "value_from_model_tables", "sql_value", "sql_source", "status"])
        w.writerows(rows_out)
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(rows_out)} checks)")
    if failures:
        print("FAILED:", failures)
        sys.exit(1)
    print("ALL DASHBOARD VALUES MATCH SQL")


if __name__ == "__main__":
    main()
