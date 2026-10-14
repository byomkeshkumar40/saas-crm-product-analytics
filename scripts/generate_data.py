#!/usr/bin/env python3
"""Generate the synthetic B2B SaaS CRM dataset (standard library only).

Outputs four normalized CSVs to data/raw/: accounts, users, events, subscriptions.
Everything is driven by SEED, so repeated runs produce identical files.

Behavioural mechanics (none of them targets a specific KPI value):
  * account engagement is lognormal, scaled by plan and industry; ~10% of accounts are "low-touch"
  * every feature has a per-account adoption date (or never), later for advanced features
  * ~28% of users are "drive-by": an onboarding burst, then rare returns
  * advanced features (Reporting, Workflow Automation) are used less in an account's first 90 days
  * weekday/weekend seasonality; ~8% of accounts churn and stop generating events
"""
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
N_ACCOUNTS = 1200
OBS_START = date(2026, 1, 1)
OBS_END = date(2026, 3, 31)  # 90-day window: Jan 1 - Mar 31 2026
N_DAYS = (OBS_END - OBS_START).days + 1
BASE_DAILY_P = 0.045  # baseline probability that a user is active on a weekday

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

FEATURES = ["Lead Management", "Contact Management", "Deal Pipeline",
            "Workflow Automation", "Reporting", "Email Integration"]
ADVANCED = {"Workflow Automation", "Reporting"}

EVENT_NAMES = {
    "Lead Management": [("lead_created", 3), ("lead_updated", 5), ("lead_converted", 1)],
    "Contact Management": [("contact_created", 2), ("contact_viewed", 6), ("contact_updated", 3)],
    "Deal Pipeline": [("deal_created", 2), ("deal_stage_changed", 5), ("deal_closed", 1)],
    "Workflow Automation": [("workflow_created", 1), ("workflow_edited", 2), ("workflow_triggered", 6)],
    "Reporting": [("report_viewed", 6), ("report_created", 1), ("report_exported", 2)],
    "Email Integration": [("email_sent", 6), ("email_synced", 3), ("email_template_used", 2)],
}
BASE_W = {"Lead Management": 22, "Contact Management": 24, "Deal Pipeline": 18,
          "Workflow Automation": 7, "Reporting": 10, "Email Integration": 16}
ROLE_W = {
    "sales_rep": {"Lead Management": 1.3, "Contact Management": 1.2, "Deal Pipeline": 1.2,
                  "Workflow Automation": 0.3, "Reporting": 0.4, "Email Integration": 1.3},
    "manager": {"Lead Management": 0.8, "Contact Management": 0.7, "Deal Pipeline": 1.4,
                "Workflow Automation": 0.6, "Reporting": 1.8, "Email Integration": 0.6},
    "admin": {"Lead Management": 0.6, "Contact Management": 0.8, "Deal Pipeline": 0.5,
              "Workflow Automation": 3.0, "Reporting": 1.0, "Email Integration": 0.7},
    "analyst": {"Lead Management": 0.5, "Contact Management": 0.6, "Deal Pipeline": 0.6,
                "Workflow Automation": 0.8, "Reporting": 3.0, "Email Integration": 0.3},
}
ROLE_ACTIVITY = {"sales_rep": 1.2, "manager": 0.8, "admin": 0.9, "analyst": 0.7}
ROLE_MIX = [("sales_rep", 0.55), ("manager", 0.20), ("admin", 0.15), ("analyst", 0.10)]

INDUSTRIES = [("Technology", .24), ("Financial Services", .14), ("Healthcare", .12),
              ("Retail & E-commerce", .16), ("Manufacturing", .10), ("Real Estate", .10),
              ("Education", .07), ("Professional Services", .07)]
INDUSTRY_ENG = {"Technology": 1.2, "Financial Services": 1.0, "Healthcare": 0.85,
                "Retail & E-commerce": 0.9, "Manufacturing": 0.7, "Real Estate": 1.1,
                "Education": 0.75, "Professional Services": 1.0}
SIZES = [("1-10", .38), ("11-50", .34), ("51-200", .20), ("201+", .08)]
PLAN_BY_SIZE = {"1-10": [("Starter", .75), ("Professional", .22), ("Enterprise", .03)],
                "11-50": [("Starter", .40), ("Professional", .50), ("Enterprise", .10)],
                "51-200": [("Starter", .12), ("Professional", .50), ("Enterprise", .38)],
                "201+": [("Starter", .03), ("Professional", .27), ("Enterprise", .70)]}
PLAN_ENG = {"Starter": 0.7, "Professional": 1.0, "Enterprise": 1.3}
PLAN_ADV_USE = {"Starter": 0.5, "Professional": 1.0, "Enterprise": 1.4}
USERS_PER_SIZE = {"1-10": (2, 4), "11-50": (3, 7), "51-200": (5, 10), "201+": (8, 14)}
REGIONS = [("North America", .42), ("Europe", .27), ("APAC", .21), ("LATAM", .07),
           ("Middle East & Africa", .03)]
# feature -> (adoption probability by plan, mean days from signup to first use)
ADOPTION = {
    "Lead Management": ({"Starter": .97, "Professional": .98, "Enterprise": .98}, 3),
    "Contact Management": ({"Starter": .99, "Professional": .99, "Enterprise": .99}, 3),
    "Deal Pipeline": ({"Starter": .88, "Professional": .93, "Enterprise": .95}, 5),
    "Email Integration": ({"Starter": .55, "Professional": .70, "Enterprise": .80}, 10),
    "Reporting": ({"Starter": .45, "Professional": .80, "Enterprise": .93}, 25),
    "Workflow Automation": ({"Starter": .12, "Professional": .50, "Enterprise": .78}, 40),
}
HOUR_W = [(7, 2), (8, 6), (9, 10), (10, 12), (11, 11), (12, 6), (13, 9),
          (14, 11), (15, 10), (16, 8), (17, 5), (18, 3), (19, 1), (20, 1)]

rng = random.Random(SEED)


def pick(items):
    return rng.choices([v for v, _ in items], weights=[w for _, w in items])[0]


def rand_dt(d, lo_h=8, hi_h=18):
    return datetime(d.year, d.month, d.day, rng.randint(lo_h, hi_h - 1),
                    rng.randint(0, 59), rng.randint(0, 59))


def build_accounts():
    accounts, subs = [], []
    sub_n = 0
    for i in range(1, N_ACCOUNTS + 1):
        if rng.random() < 0.28:
            signup = OBS_START + timedelta(days=rng.randint(0, N_DAYS - 3))
        else:
            span = (OBS_START - date(2024, 1, 1)).days
            signup = date(2024, 1, 1) + timedelta(days=rng.randint(0, span - 1))
        size = pick(SIZES)
        industry = pick(INDUSTRIES)
        plan = pick(PLAN_BY_SIZE[size])
        eng = rng.lognormvariate(0, 0.7) * PLAN_ENG[plan] * INDUSTRY_ENG[industry]
        if rng.random() < 0.10:
            eng *= 0.1  # low-touch account
        churn = None
        if rng.random() < 0.08:
            if signup < OBS_START:
                churn = OBS_START + timedelta(days=rng.randint(0, N_DAYS - 5))
            else:
                c = signup + timedelta(days=rng.randint(7, 60))
                churn = c if c <= OBS_END else None
        adopt = {}
        for f, (probs, mean_delay) in ADOPTION.items():
            adopt[f] = (signup + timedelta(days=int(rng.expovariate(1 / mean_delay)))
                        if rng.random() < probs[plan] else None)
        acct = {
            "account_id": f"A{i:04d}", "signup_date": signup, "industry": industry,
            "company_size": size, "subscription_plan": plan, "region": pick(REGIONS),
            "eng": eng, "trend": rng.uniform(-0.5, 0.5), "churn": churn, "adopt": adopt,
            "aff": {f: rng.lognormvariate(0, 0.4) for f in FEATURES},
        }
        accounts.append(acct)

        if churn is not None:
            status = "cancelled"
        elif signup >= OBS_END - timedelta(days=13) and rng.random() < 0.6:
            status = "trial"
        else:
            status = "past_due" if rng.random() < 0.03 else "active"
        rows = [(signup, plan, status)]
        if plan != "Starter" and rng.random() < 0.18 and (OBS_END - signup).days > 40:
            prev = "Starter" if plan == "Professional" else "Professional"
            up = signup + timedelta(days=rng.randint(30, min(400, (OBS_END - signup).days)))
            rows = [(signup, prev, "replaced"), (up, plan, status)]
        for start, p, st in rows:
            sub_n += 1
            subs.append({"subscription_id": f"S{sub_n:05d}", "account_id": acct["account_id"],
                         "plan": p, "subscription_start": start, "subscription_status": st})
    return accounts, subs


def build_users(accounts):
    users = []
    n = 0
    for a in accounts:
        lo, hi = USERS_PER_SIZE[a["company_size"]]
        for k in range(rng.randint(lo, hi)):
            n += 1
            if k == 0:
                created = rand_dt(a["signup_date"])
                role = "admin"
            else:
                role = pick(ROLE_MIX)
                if a["signup_date"] >= OBS_START:
                    day = a["signup_date"] + timedelta(days=int(rng.expovariate(1 / 10)))
                elif rng.random() < 0.70:
                    span = (OBS_START - a["signup_date"]).days
                    day = a["signup_date"] + timedelta(days=rng.randint(0, max(span - 1, 0)))
                else:
                    day = OBS_START + timedelta(days=rng.randint(0, N_DAYS - 1))
                day = min(day, OBS_END)
                created = rand_dt(day)
            users.append({
                "user_id": f"U{n:05d}", "account_id": a["account_id"], "created_at": created,
                "user_role": role,
                "eng": 0.06 if rng.random() < 0.28 else rng.lognormvariate(0, 0.5),
            })
    return users


def feature_weights(a, role, d):
    age = (d - a["signup_date"]).days
    w = []
    for f in FEATURES:
        ad = a["adopt"][f]
        if ad is None or d < ad:
            w.append(0.0)
            continue
        x = BASE_W[f] * ROLE_W[role][f] * a["aff"][f]
        if f in ADVANCED:
            x *= PLAN_ADV_USE[a["subscription_plan"]]
            x *= 0.5 if age < 30 else (0.8 if age < 90 else 1.0)
        w.append(x)
    return w


def build_events(accounts, users):
    by_id = {a["account_id"]: a for a in accounts}
    events = []
    ses_n = 0
    for u in users:
        a = by_id[u["account_id"]]
        c_date = u["created_at"].date()
        last = min(OBS_END, a["churn"] - timedelta(days=1)) if a["churn"] else OBS_END
        for di in range(N_DAYS):
            d = OBS_START + timedelta(days=di)
            if d < c_date or d > last:
                continue
            wk = d.weekday()
            season = 1.0 if wk < 5 else (0.25 if wk == 5 else 0.20)
            u_age = (d - c_date).days
            burst = 4.0 if u_age <= 2 else (2.0 if u_age <= 13 else 1.0)
            trend = max(0.2, 1 + a["trend"] * (di / N_DAYS - 0.5) * 2)
            p = min(0.9, BASE_DAILY_P * a["eng"] * u["eng"] * ROLE_ACTIVITY[u["user_role"]]
                    * season * burst * trend)
            if rng.random() >= p:
                continue
            for _ in range(1 + (rng.random() < 0.25)):
                w = feature_weights(a, u["user_role"], d)
                if sum(w) == 0:
                    break
                primary = rng.choices(FEATURES, weights=w)[0]
                start = rand_dt(d, 7, 8)
                start = start.replace(hour=pick(HOUR_W))
                if d == c_date and start <= u["created_at"]:
                    start = u["created_at"] + timedelta(seconds=rng.randint(60, 3600))
                if start.date() != d or start.hour > 21:
                    continue
                ses_n += 1
                ses = f"SES{ses_n:07d}"
                ts = start
                for _e in range(rng.randint(2, 6)):
                    f = primary if rng.random() < 0.6 else rng.choices(FEATURES, weights=w)[0]
                    names = EVENT_NAMES[f]
                    events.append({
                        "event_timestamp": ts, "user_id": u["user_id"],
                        "account_id": a["account_id"], "event_name": pick(names),
                        "feature_name": f, "session_id": ses})
                    ts += timedelta(seconds=rng.randint(15, 240))
    events.sort(key=lambda e: (e["event_timestamp"], e["user_id"]))
    for i, e in enumerate(events, 1):
        e["event_id"] = f"E{i:07d}"
    return events


def write_csv(name, rows, cols):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_DIR / name, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(cols)
        for r in rows:
            wr.writerow([r[c].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r[c], datetime)
                         else r[c].isoformat() if isinstance(r[c], date) else r[c] for c in cols])


def main():
    accounts, subs = build_accounts()
    users = build_users(accounts)
    events = build_events(accounts, users)
    write_csv("accounts.csv", accounts, ["account_id", "signup_date", "industry", "company_size",
                                         "subscription_plan", "region"])
    write_csv("users.csv", users, ["user_id", "account_id", "created_at", "user_role"])
    write_csv("events.csv", events, ["event_id", "user_id", "account_id", "event_timestamp",
                                     "event_name", "feature_name", "session_id"])
    write_csv("subscriptions.csv", subs, ["subscription_id", "account_id", "plan",
                                          "subscription_start", "subscription_status"])
    print(f"seed={SEED} accounts={len(accounts)} users={len(users)} "
          f"events={len(events)} subscriptions={len(subs)}")


if __name__ == "__main__":
    main()
