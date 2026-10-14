"""KPI calculations. Pure pandas (no Streamlit) so they can be validated against the SQL results.

Definitions are identical to sql/product_analysis.sql / reports/kpi_definitions.md. A "Scope" is the dataset
after the sidebar filters:
  * plan / industry / company size   -> restrict the accounts (and their users and events)
  * date range                       -> restricts events (and "accounts / users that exist by range end")
Metrics whose definition is tied to a fixed calendar (activation cohort, 30-day new-vs-established exposure,
inactive = silent in the last 30 days of the window) ignore the date range and say so in the UI.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import FEATURES, Dataset


@dataclass(frozen=True)
class Filters:
    plans: tuple
    industries: tuple
    sizes: tuple
    start: pd.Timestamp
    end: pd.Timestamp


@dataclass
class Scope:
    ds: Dataset
    f: Filters
    accounts: pd.DataFrame    # accounts passing plan/industry/size filters (any signup date)
    users: pd.DataFrame       # users of those accounts
    events_all: pd.DataFrame  # events of those accounts, whole observation window
    events: pd.DataFrame      # events of those accounts inside the selected date range

    @property
    def full_range(self):
        return self.f.start == self.ds.d0 and self.f.end == self.ds.d1


def build_scope(ds: Dataset, f: Filters) -> Scope:
    a = ds.accounts
    acc = a[a.subscription_plan.isin(f.plans) & a.industry.isin(f.industries) & a.company_size.isin(f.sizes)]
    ids = acc.account_id
    ev_all = ds.events[ds.events.account_id.isin(ids)]
    ev = ev_all[(ev_all.event_date >= f.start) & (ev_all.event_date <= f.end)]
    return Scope(ds, f, acc, ds.users[ds.users.account_id.isin(ids)], ev_all, ev)


def pct(n, d):
    return float(100.0 * n / d) if d else float("nan")


# ------------------------------------------------------------------ DAU / MAU
def daily_series(s: Scope) -> pd.DataFrame:
    """DAU per calendar day for the whole window (zero days included), then cut to the date range.
    The 7-day average is computed on the whole window first so it matches SQL q01 inside any range."""
    days = pd.date_range(s.ds.d0, s.ds.d1)
    g = s.events_all.groupby("event_date").agg(
        dau=("user_id", "nunique"), events=("event_id", "count"),
        active_accounts=("account_id", "nunique"))
    df = g.reindex(days, fill_value=0)
    df.index.name = "date"
    df = df.reset_index()
    df["dau_7d_avg"] = df["dau"].rolling(7, min_periods=1).mean()
    df["events_7d_avg"] = df["events"].rolling(7, min_periods=1).mean()
    df["active_accounts_7d_avg"] = df["active_accounts"].rolling(7, min_periods=1).mean()
    return df[(df.date >= s.f.start) & (df.date <= s.f.end)].reset_index(drop=True)


def monthly_series(s: Scope) -> pd.DataFrame:
    """MAU and DAU/MAU per calendar month, using only days inside the date range (partial = month not fully covered)."""
    daily = daily_series(s).set_index("date")
    rows = []
    for period in pd.period_range(s.f.start, s.f.end, freq="M"):
        m0, m1 = period.start_time.normalize(), period.end_time.normalize()
        lo, hi = max(m0, s.f.start), min(m1, s.f.end)
        days = pd.date_range(lo, hi)
        mau = s.events[(s.events.event_date >= lo) & (s.events.event_date <= hi)].user_id.nunique()
        avg_dau = float(daily.loc[days, "dau"].mean())
        rows.append({"month": str(period), "days_covered": len(days), "days_in_month": (m1 - m0).days + 1,
                     "partial": len(days) < (m1 - m0).days + 1, "mau": mau, "avg_dau": avg_dau,
                     "dau_mau_ratio": avg_dau / mau if mau else float("nan")})
    return pd.DataFrame(rows)


def overview_kpis(s: Scope) -> dict:
    daily = daily_series(s)
    monthly = monthly_series(s)
    last = monthly.iloc[-1]
    return {
        "total_accounts": int((s.accounts.signup_date <= s.f.end).sum()),
        "total_users": int((s.users.created_date <= s.f.end).sum()),
        "active_users": int(s.events.user_id.nunique()),
        "active_accounts": int(s.events.account_id.nunique()),
        "avg_dau": float(daily["dau"].mean()),
        "mau": int(last["mau"]),
        "mau_month": last["month"],
        "mau_partial": bool(last["partial"]),
        "dau_mau_ratio": float(last["dau_mau_ratio"]),
        "days": len(daily),
    }


# ------------------------------------------------------------------ activation (fixed 14-day cohort definition)
def activation_accounts(s: Scope) -> pd.DataFrame:
    """Cohort: signed up in the window with >= 14 observed days. Activated: first 14 days have >= 2 users and >= 3 features."""
    a = s.accounts
    cohort = a[(a.signup_date >= s.ds.d0) & (a.signup_date <= s.ds.d1 - pd.Timedelta(days=13))][
        ["account_id", "signup_date", "subscription_plan", "industry", "company_size"]]
    ev = s.events_all.merge(cohort[["account_id", "signup_date"]], on="account_id")
    ev = ev[(ev.event_date >= ev.signup_date) & (ev.event_date < ev.signup_date + pd.Timedelta(days=14))]
    g = ev.groupby("account_id").agg(early_users=("user_id", "nunique"), early_features=("feature_name", "nunique"))
    c = cohort.merge(g, on="account_id", how="left")
    c[["early_users", "early_features"]] = c[["early_users", "early_features"]].fillna(0).astype(int)
    c["activated"] = (c.early_users >= 2) & (c.early_features >= 3)
    return c


def activation_summary(c: pd.DataFrame, by: str = None) -> pd.DataFrame:
    if by is None:
        out = pd.DataFrame({"segment": ["All"], "cohort_accounts": [len(c)], "activated_accounts": [int(c.activated.sum())]})
    else:
        out = (c.groupby(by).agg(cohort_accounts=("account_id", "count"), activated_accounts=("activated", "sum"))
               .reset_index().rename(columns={by: "segment"}))
    out["activation_rate_pct"] = [pct(a, n) for a, n in zip(out.activated_accounts, out.cohort_accounts)]
    return out


# ------------------------------------------------------------------ feature adoption / usage (selected date range)
def feature_adoption(s: Scope) -> pd.DataFrame:
    ev = s.events
    n_acc, n_usr = ev.account_id.nunique(), ev.user_id.nunique()
    g = ev.groupby("feature_name").agg(events=("event_id", "count"), accounts_using=("account_id", "nunique"),
                                       users_using=("user_id", "nunique")).reindex(FEATURES).fillna(0).astype(int)
    g["active_accounts"], g["active_users"] = n_acc, n_usr
    g["account_adoption_pct"] = [pct(x, n_acc) for x in g.accounts_using]
    g["user_adoption_pct"] = [pct(x, n_usr) for x in g.users_using]
    g["pct_of_all_events"] = [pct(x, len(ev)) for x in g.events]
    g["events_per_using_user"] = [x / u if u else float("nan") for x, u in zip(g.events, g.users_using)]
    return g.reset_index()


def feature_by_plan(s: Scope) -> pd.DataFrame:
    ev = s.events
    plan_acc = ev.groupby("subscription_plan").account_id.nunique().rename("active_accounts")
    plan_ev = ev.groupby("subscription_plan").size().rename("plan_events")
    g = ev.groupby(["subscription_plan", "feature_name"]).agg(
        adopting_accounts=("account_id", "nunique"), events=("event_id", "count")).reset_index()
    g = g.join(plan_acc, on="subscription_plan").join(plan_ev, on="subscription_plan")
    g["adoption_pct"] = 100.0 * g.adopting_accounts / g.active_accounts
    g["pct_of_plan_events"] = 100.0 * g.events / g.plan_events
    return g


def new_vs_established(s: Scope) -> pd.DataFrame:
    """Fixed 30-day exposure. New: signed up in window, signup <= end-29d, exposure signup..+29.
    Established: signed up before window, exposure = first 30 days of the window."""
    a = s.accounts
    d0, d1 = s.ds.d0, s.ds.d1
    est = a[a.signup_date < d0].assign(cohort="Established (signed up before window)", exp_start=d0)
    new = a[(a.signup_date >= d0) & (a.signup_date <= d1 - pd.Timedelta(days=29))].assign(
        cohort="New (signed up in window)", exp_start=lambda x: x.signup_date)
    elig = pd.concat([est, new])[["account_id", "cohort", "exp_start"]]
    ev = s.events_all.merge(elig, on="account_id")
    ev = ev[(ev.event_date >= ev.exp_start) & (ev.event_date < ev.exp_start + pd.Timedelta(days=30))]
    base = ev.groupby("cohort").account_id.nunique().rename("active_accounts")
    ad = ev.drop_duplicates(["account_id", "feature_name"]).groupby(["cohort", "feature_name"]).size().rename("adopting_accounts")
    idx = pd.MultiIndex.from_product([base.index, FEATURES], names=["cohort", "feature_name"])
    out = ad.reindex(idx, fill_value=0).reset_index().join(base, on="cohort")
    out["eligible_accounts"] = out.cohort.map(elig.groupby("cohort").size())
    out["adoption_pct"] = 100.0 * out.adopting_accounts / out.active_accounts
    return out


# ------------------------------------------------------------------ inactivity (fixed: last 30 days of the window)
def inactive_accounts(s: Scope) -> pd.DataFrame:
    """Eligible = signup <= window_end - 29d. Inactive = no events from window_end-29d to window_end."""
    cut = s.ds.d1 - pd.Timedelta(days=29)
    a = s.accounts[s.accounts.signup_date <= cut].copy()
    stats = s.events_all.groupby("account_id").agg(events_in_window=("event_id", "count"),
                                                   last_event_date=("event_date", "max"))
    recent = set(s.events_all[s.events_all.event_date >= cut].account_id)
    a = a.join(stats, on="account_id")
    a["events_in_window"] = a.events_in_window.fillna(0).astype(int)
    a["inactive"] = ~a.account_id.isin(recent)
    a["never_active"] = a.events_in_window == 0
    a["inactivity_type"] = np.where(~a.inactive, "Active", np.where(a.never_active, "Never active in window",
                                    "Lapsed (active earlier, none in last 30 days)"))
    return a


def inactive_summary(a: pd.DataFrame, by: str = None) -> pd.DataFrame:
    a = a.assign(lapsed=a.inactive & ~a.never_active, never=a.inactive & a.never_active)
    if by is None:
        a = a.assign(segment="All")
        by = "segment"
    g = a.groupby(by).agg(eligible_accounts=("account_id", "count"), inactive_accounts=("inactive", "sum"),
                          never_active_accounts=("never", "sum"), lapsed_accounts=("lapsed", "sum")).reset_index()
    g = g.rename(columns={by: "segment"})
    g["inactive_pct"] = [pct(i, e) for i, e in zip(g.inactive_accounts, g.eligible_accounts)]
    g["never_pct"] = [pct(i, e) for i, e in zip(g.never_active_accounts, g.eligible_accounts)]
    g["lapsed_pct"] = [pct(i, e) for i, e in zip(g.lapsed_accounts, g.eligible_accounts)]
    return g


# ------------------------------------------------------------------ segment engagement (selected date range)
def segment_engagement(s: Scope, by: str) -> pd.DataFrame:
    """Same definitions as SQL q08/q09/q09b. Exposure = days the account existed inside the date range."""
    a = s.accounts[s.accounts.signup_date <= s.f.end].copy()
    a["exposure_days"] = (s.f.end - a.signup_date.clip(lower=s.f.start)).dt.days + 1
    ev = s.events.groupby("account_id").agg(events=("event_id", "count"), active_users=("user_id", "nunique"))
    nu = s.users[s.users.created_date <= s.f.end].groupby("account_id").size().rename("n_users")
    a = a.join(ev, on="account_id").join(nu, on="account_id")
    a[["events", "active_users", "n_users"]] = a[["events", "active_users", "n_users"]].fillna(0)
    a["is_active"] = a.events > 0
    g = a.groupby(by).agg(accounts=("account_id", "count"), active_accounts=("is_active", "sum"),
                          total_users=("n_users", "sum"), active_users=("active_users", "sum"),
                          events=("events", "sum"), exposure_days=("exposure_days", "sum")).reset_index()
    g = g.rename(columns={by: "segment"})
    g["pct_accounts_active"] = [pct(x, n) for x, n in zip(g.active_accounts, g.accounts)]
    g["pct_users_active"] = [pct(x, n) for x, n in zip(g.active_users, g.total_users)]
    g["events_per_account_30d"] = 30.0 * g.events / g.exposure_days
    g["events_per_active_user"] = [e / u if u else float("nan") for e, u in zip(g.events, g.active_users)]
    return g


def users_by_plan(s: Scope) -> pd.DataFrame:
    """Active vs not-active users by plan (users existing by range end; active = >= 1 event in range)."""
    a = segment_engagement(s, "subscription_plan")
    a["not_active_users"] = a.total_users - a.active_users
    return a
