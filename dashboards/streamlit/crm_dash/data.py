"""Data loading. Reads the existing SQLite database built by scripts/run_analysis.py (nothing is generated here)."""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]  # project root, independent of the working directory
DB_PATH = ROOT / "data" / "processed" / "crm_analytics.db"
KPI_DIR = ROOT / "data" / "processed" / "kpi_tables"

FEATURES = ["Lead Management", "Contact Management", "Deal Pipeline",
            "Email Integration", "Reporting", "Workflow Automation"]
PLAN_ORDER = ["Starter", "Professional", "Enterprise"]
SIZE_ORDER = ["1-10", "11-50", "51-200", "201+"]


class MissingDataError(FileNotFoundError):
    pass


@dataclass
class Dataset:
    accounts: pd.DataFrame
    users: pd.DataFrame
    events: pd.DataFrame  # denormalised with plan / industry / company_size of the account
    d0: pd.Timestamp      # observation window start (analysis_params.obs_start)
    d1: pd.Timestamp      # observation window end   (analysis_params.obs_end)


def load_dataset(db_path: Path = DB_PATH) -> Dataset:
    if not Path(db_path).exists():
        raise MissingDataError(
            f"SQLite database not found: {db_path}\n"
            "Build it from the project root with:\n"
            "  python scripts/generate_data.py && python scripts/run_analysis.py")
    con = sqlite3.connect(db_path)
    try:
        start, end = con.execute("SELECT obs_start, obs_end FROM analysis_params").fetchone()
        accounts = pd.read_sql_query("SELECT * FROM accounts", con)
        users = pd.read_sql_query("SELECT * FROM users", con)
        events = pd.read_sql_query("SELECT * FROM events", con)
        subs = pd.read_sql_query("SELECT account_id, subscription_start, subscription_status "
                                 "FROM subscriptions", con)
    finally:
        con.close()
    accounts["signup_date"] = pd.to_datetime(accounts["signup_date"])
    latest = (subs.sort_values("subscription_start").groupby("account_id").tail(1)
              .rename(columns={"subscription_status": "latest_subscription_status"}))
    accounts = accounts.merge(latest[["account_id", "latest_subscription_status"]],
                              on="account_id", how="left")
    users["created_at"] = pd.to_datetime(users["created_at"])
    users["created_date"] = users["created_at"].dt.normalize()
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"])
    events["event_date"] = events["event_timestamp"].dt.normalize()
    events = events.merge(accounts[["account_id", "subscription_plan", "industry", "company_size"]],
                          on="account_id", how="left")
    return Dataset(accounts, users, events, pd.Timestamp(start), pd.Timestamp(end))
