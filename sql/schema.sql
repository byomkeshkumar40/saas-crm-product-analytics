-- SaaS CRM Product Usage & Feature Adoption Analysis
-- SQLite schema. Dates are ISO text: DATE = 'YYYY-MM-DD', TIMESTAMP = 'YYYY-MM-DD HH:MM:SS'.

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_account_stats;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS analysis_params;

-- One-row table holding the 90-day observation window used by every query.
CREATE TABLE analysis_params (
    obs_start TEXT NOT NULL,
    obs_end   TEXT NOT NULL
);
INSERT INTO analysis_params VALUES ('2026-01-01', '2026-03-31');

CREATE TABLE accounts (
    account_id        TEXT PRIMARY KEY,
    signup_date       TEXT NOT NULL,
    industry          TEXT NOT NULL,
    company_size      TEXT NOT NULL CHECK (company_size IN ('1-10','11-50','51-200','201+')),
    subscription_plan TEXT NOT NULL CHECK (subscription_plan IN ('Starter','Professional','Enterprise')),
    region            TEXT NOT NULL
);

CREATE TABLE users (
    user_id    TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    created_at TEXT NOT NULL,
    user_role  TEXT NOT NULL CHECK (user_role IN ('admin','manager','sales_rep','analyst'))
);

CREATE TABLE subscriptions (
    subscription_id     TEXT PRIMARY KEY,
    account_id          TEXT NOT NULL REFERENCES accounts(account_id),
    plan                TEXT NOT NULL CHECK (plan IN ('Starter','Professional','Enterprise')),
    subscription_start  TEXT NOT NULL,
    subscription_status TEXT NOT NULL CHECK (subscription_status IN
                        ('active','trial','past_due','cancelled','replaced'))
);

CREATE TABLE events (
    event_id        TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    account_id      TEXT NOT NULL REFERENCES accounts(account_id),
    event_timestamp TEXT NOT NULL,
    event_name      TEXT NOT NULL,
    feature_name    TEXT NOT NULL CHECK (feature_name IN
                    ('Lead Management','Contact Management','Deal Pipeline',
                     'Workflow Automation','Reporting','Email Integration')),
    session_id      TEXT NOT NULL
);

CREATE INDEX idx_users_account   ON users(account_id);
CREATE INDEX idx_subs_account    ON subscriptions(account_id);
CREATE INDEX idx_events_user     ON events(user_id);
CREATE INDEX idx_events_account  ON events(account_id);
CREATE INDEX idx_events_ts       ON events(event_timestamp);

-- Per-account roll-up over the observation window.
--   events / active_users / features_used / active_days count only events inside the window.
--   exposure_days = days the account existed inside the window (inclusive); used to normalise
--   accounts that signed up mid-window.
CREATE VIEW v_account_stats AS
SELECT a.account_id,
       a.signup_date,
       a.subscription_plan,
       a.industry,
       a.company_size,
       a.region,
       (SELECT COUNT(*) FROM users u WHERE u.account_id = a.account_id) AS n_users,
       COUNT(e.event_id)                                  AS events,
       COUNT(DISTINCT e.user_id)                          AS active_users,
       COUNT(DISTINCT e.feature_name)                     AS features_used,
       COUNT(DISTINCT date(e.event_timestamp))            AS active_days,
       MAX(date(e.event_timestamp))                       AS last_event_date,
       CAST(julianday(p.obs_end) - julianday(MAX(a.signup_date, p.obs_start)) AS INTEGER) + 1
                                                          AS exposure_days
FROM accounts a
CROSS JOIN analysis_params p
LEFT JOIN events e ON e.account_id = a.account_id
GROUP BY a.account_id, p.obs_start, p.obs_end;
