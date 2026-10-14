#!/usr/bin/env python3
"""Validate the raw data and cross-check the SQL KPI outputs (standard library only).

Part 1 - raw data integrity (data/raw/*.csv)
  unique IDs, foreign keys, timestamp format and window, event/user/account chronology,
  feature <-> event_name consistency, session ownership, subscription/plan consistency, size targets.
Part 2 - KPI cross-check (needs data/processed/kpi_tables from run_analysis.py)
  recomputes headline KPIs from the raw CSVs in plain Python and compares them with the SQL results.
Exit code is non-zero if any check fails.
"""
import csv
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
KPI = ROOT / "data" / "processed" / "kpi_tables"
OBS_START, OBS_END = date(2026, 1, 1), date(2026, 3, 31)
FEATURES = {"Lead Management", "Contact Management", "Deal Pipeline",
            "Workflow Automation", "Reporting", "Email Integration"}
failures = []


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(label)


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(n, d):
    return round(100.0 * n / d, 1)


def main():
    accounts, users = read(RAW / "accounts.csv"), read(RAW / "users.csv")
    events, subs = read(RAW / "events.csv"), read(RAW / "subscriptions.csv")

    print("== Part 1: raw data integrity")
    check("accounts >= 1,000 (target ~1,200)", len(accounts) >= 1000, str(len(accounts)))
    check("events >= 25,000", len(events) >= 25000, str(len(events)))
    for name, rows, key in [("accounts", accounts, "account_id"), ("users", users, "user_id"),
                            ("events", events, "event_id"), ("subscriptions", subs, "subscription_id")]:
        ids = [r[key] for r in rows]
        check(f"{name}.{key} unique", len(ids) == len(set(ids)))

    acc = {a["account_id"]: a for a in accounts}
    usr = {u["user_id"]: u for u in users}
    check("users.account_id -> accounts", all(u["account_id"] in acc for u in users))
    check("subscriptions.account_id -> accounts", all(s["account_id"] in acc for s in subs))
    check("events.user_id -> users", all(e["user_id"] in usr for e in events))
    check("events.account_id -> accounts", all(e["account_id"] in acc for e in events))
    check("events.account_id matches the user's account",
          all(usr[e["user_id"]]["account_id"] == e["account_id"] for e in events))
    per_acct = defaultdict(int)
    for u in users:
        per_acct[u["account_id"]] += 1
    check("every account has >= 2 users", all(per_acct[a] >= 2 for a in acc))

    fmt_ok, in_window, after_user, after_acct = True, True, True, True
    for e in events:
        try:
            ts = datetime.strptime(e["event_timestamp"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            fmt_ok = False
            continue
        in_window &= OBS_START <= ts.date() <= OBS_END
        after_user &= ts > datetime.strptime(usr[e["user_id"]]["created_at"], "%Y-%m-%d %H:%M:%S")
        after_acct &= ts.date() >= date.fromisoformat(acc[e["account_id"]]["signup_date"])
    check("event_timestamp format YYYY-MM-DD HH:MM:SS", fmt_ok)
    check("event_timestamp inside 2026-01-01..2026-03-31", in_window)
    check("event_timestamp after user created_at", after_user)
    check("event_timestamp on/after account signup_date", after_acct)
    check("users.created_at on/after account signup_date and <= window end",
          all(date.fromisoformat(u["created_at"][:10]) >= date.fromisoformat(acc[u["account_id"]]["signup_date"])
              and date.fromisoformat(u["created_at"][:10]) <= OBS_END for u in users))
    check("feature_name in the six CRM features", all(e["feature_name"] in FEATURES for e in events))
    names = defaultdict(set)
    for e in events:
        names[e["event_name"]].add(e["feature_name"])
    check("each event_name belongs to exactly one feature", all(len(v) == 1 for v in names.values()))
    ses = defaultdict(set)
    for e in events:
        ses[e["session_id"]].add(e["user_id"])
    check("each session_id belongs to a single user", all(len(v) == 1 for v in ses.values()))
    cur_plan = {}
    for s in sorted(subs, key=lambda s: s["subscription_start"]):
        cur_plan[s["account_id"]] = s["plan"]
    check("latest subscription plan == accounts.subscription_plan",
          all(cur_plan[a] == acc[a]["subscription_plan"] for a in acc))
    check("every account has a subscription", set(cur_plan) == set(acc))
    check("subscription_start on/after signup_date",
          all(s["subscription_start"] >= acc[s["account_id"]]["signup_date"] for s in subs))

    print("\n== Part 2: KPI cross-check (SQL output vs independent Python recomputation)")
    if not (KPI / "q00_overview.csv").exists():
        check("KPI tables exist (run scripts/run_analysis.py first)", False)
        return
    ov = read(KPI / "q00_overview.csv")[0]
    dau = defaultdict(set)
    mau = defaultdict(set)
    for e in events:
        dau[e["event_timestamp"][:10]].add(e["user_id"])
        mau[e["event_timestamp"][:7]].add(e["user_id"])
    active_users = {e["user_id"] for e in events}
    active_accts = {e["account_id"] for e in events}
    avg_dau = sum(len(v) for v in dau.values()) / 90
    check("total_accounts", int(ov["total_accounts"]) == len(accounts))
    check("active_users_90d", int(ov["active_users_90d"]) == len(active_users))
    check("active_accounts_90d", int(ov["active_accounts_90d"]) == len(active_accts))
    check("avg_dau (90-day mean, zero days included)", abs(float(ov["avg_dau"]) - avg_dau) < 0.06,
          f"{ov['avg_dau']} vs {avg_dau:.2f}")
    check("mau_latest_month (2026-03)", int(ov["mau_latest_month"]) == len(mau["2026-03"]))
    for r in read(KPI / "q02_mau.csv"):
        check(f"MAU {r['month']}", int(r["mau"]) == len(mau[r["month"]]))
    q01 = read(KPI / "q01_dau.csv")
    check("DAU table has 90 consecutive days", len(q01) == 90)
    check("DAU values match", all(int(r["dau"]) == len(dau.get(r["activity_date"], ())) for r in q01))
    for r in read(KPI / "q03_dau_mau_ratio.csv"):
        m = r["month"]
        days = [d for d in (OBS_START + timedelta(n) for n in range(90)) if d.isoformat()[:7] == m]
        ratio = sum(len(dau.get(d.isoformat(), ())) for d in days) / len(days) / len(mau[m])
        check(f"DAU/MAU {m}", abs(float(r["dau_mau_ratio"]) - ratio) < 0.0001, f"{r['dau_mau_ratio']} vs {ratio:.4f}")
        check(f"DAU/MAU {m} within (0,1]", 0 < ratio <= 1)

    # activation
    cohort = [a for a in accounts if OBS_START <= date.fromisoformat(a["signup_date"]) <= OBS_END - timedelta(13)]
    early = defaultdict(lambda: (set(), set()))
    cset = {a["account_id"]: date.fromisoformat(a["signup_date"]) for a in cohort}
    for e in events:
        s = cset.get(e["account_id"])
        if s and s <= date.fromisoformat(e["event_timestamp"][:10]) < s + timedelta(14):
            early[e["account_id"]][0].add(e["user_id"])
            early[e["account_id"]][1].add(e["feature_name"])
    activated = sum(1 for a in cset if len(early[a][0]) >= 2 and len(early[a][1]) >= 3)
    check("activation cohort size", int(ov["activation_cohort_accounts"]) == len(cohort), str(len(cohort)))
    check("activated accounts", int(ov["activated_accounts"]) == activated, str(activated))
    check("activation rate", float(ov["activation_rate_pct"]) == pct(activated, len(cohort)))
    check("activation denominator > 0 and activated <= cohort", 0 < len(cohort) and activated <= len(cohort))

    # feature adoption (account- and user-level)
    fa, fu = defaultdict(set), defaultdict(set)
    for e in events:
        fa[e["feature_name"]].add(e["account_id"])
        fu[e["feature_name"]].add(e["user_id"])
    for r in read(KPI / "q05_feature_adoption.csv"):
        f = r["feature_name"]
        check(f"adoption {f} (account, % of active accounts)",
              float(r["account_adoption_pct_of_active_accounts"]) == pct(len(fa[f]), len(active_accts)))
        check(f"adoption {f} (user, % of active users)",
              float(r["user_adoption_pct_of_active_users"]) == pct(len(fu[f]), len(active_users)))
    ev_by_f = defaultdict(int)
    for e in events:
        ev_by_f[e["feature_name"]] += 1
    check("feature event counts sum to total events",
          sum(int(r["events"]) for r in read(KPI / "q06_feature_usage_frequency.csv")) == len(events))
    check("feature event counts match", all(int(r["events"]) == ev_by_f[r["feature_name"]]
          for r in read(KPI / "q06_feature_usage_frequency.csv")))

    # segment roll-ups must reconcile to totals
    for q in ("q08_engagement_by_plan", "q09_engagement_by_industry", "q09b_engagement_by_company_size"):
        rows = read(KPI / f"{q}.csv")
        check(f"{q}: accounts sum to total", sum(int(r["accounts"]) for r in rows) == len(accounts))
        check(f"{q}: events sum to total", sum(int(r["events"]) for r in rows) == len(events))
        check(f"{q}: active accounts sum to total", sum(int(r["active_accounts"]) for r in rows) == len(active_accts))

    # inactive accounts
    last30 = OBS_END - timedelta(29)
    recent = {e["account_id"] for e in events if date.fromisoformat(e["event_timestamp"][:10]) >= last30}
    elig = [a for a in accounts if date.fromisoformat(a["signup_date"]) <= last30]
    inactive = [a for a in elig if a["account_id"] not in recent]
    check("inactive accounts count", len(read(KPI / "q10_inactive_accounts.csv")) == len(inactive), str(len(inactive)))
    summ = read(KPI / "q10b_inactive_summary.csv")[0]
    check("inactive summary eligible/inactive", (int(summ["eligible_accounts"]), int(summ["inactive_accounts"])) == (len(elig), len(inactive)))

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
