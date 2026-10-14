-- SaaS CRM Product Usage & Feature Adoption Analysis -- SQLite
-- Run after sql/schema.sql and loading data/raw/*.csv (scripts/run_analysis.py does all of it).
--
-- Conventions
--   * Observation window = analysis_params (2026-01-01 .. 2026-03-31, 90 days). Its bounds are read
--     into the CTE "p" (d0 = start, d1 = end) in every query.
--   * "Active" always means >= 1 event. Event dates are date(event_timestamp).
--   * Every ratio's numerator and denominator are named in the output columns.
--   * Each block starts with a "-- name:" marker; scripts/run_analysis.py runs each block and
--     exports it to CSV. Blocks named model_* are the Power BI model tables.

-- name: q00_overview
-- Page-1 KPI row. avg_dau = mean of daily distinct active users over all 90 calendar days
-- (zero-activity days included). mau_latest_month = distinct active users in the last calendar
-- month of the window. Activation uses the 14-day definition from q04.
WITH RECURSIVE p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
cal(d) AS (SELECT d0 FROM p UNION ALL SELECT date(d, '+1 day') FROM cal, p WHERE d < p.d1),
daily AS (SELECT date(event_timestamp) AS d, COUNT(DISTINCT user_id) AS dau
          FROM events GROUP BY 1),
act AS (
  SELECT a.account_id,
         COUNT(DISTINCT e.user_id) AS early_users,
         COUNT(DISTINCT e.feature_name) AS early_features
  FROM accounts a CROSS JOIN p
  LEFT JOIN events e ON e.account_id = a.account_id
       AND date(e.event_timestamp) >= a.signup_date
       AND date(e.event_timestamp) < date(a.signup_date, '+14 days')
  WHERE a.signup_date BETWEEN p.d0 AND date(p.d1, '-13 days')
  GROUP BY a.account_id)
SELECT (SELECT COUNT(*) FROM accounts)                                  AS total_accounts,
       (SELECT COUNT(*) FROM users)                                     AS total_users,
       (SELECT COUNT(DISTINCT user_id) FROM events)                     AS active_users_90d,
       ROUND(100.0 * (SELECT COUNT(DISTINCT user_id) FROM events)
             / (SELECT COUNT(*) FROM users), 1)                         AS active_users_pct_of_total_users,
       (SELECT COUNT(DISTINCT account_id) FROM events)                  AS active_accounts_90d,
       ROUND((SELECT AVG(COALESCE(dl.dau, 0)) FROM cal c LEFT JOIN daily dl ON dl.d = c.d), 1)
                                                                        AS avg_dau,
       (SELECT COUNT(DISTINCT user_id) FROM events, p
         WHERE date(event_timestamp) >= strftime('%Y-%m-01', p.d1))     AS mau_latest_month,
       (SELECT COUNT(*) FROM act)                                       AS activation_cohort_accounts,
       (SELECT COUNT(*) FROM act WHERE early_users >= 2 AND early_features >= 3)
                                                                        AS activated_accounts,
       ROUND(100.0 * (SELECT COUNT(*) FROM act WHERE early_users >= 2 AND early_features >= 3)
             / (SELECT COUNT(*) FROM act), 1)                           AS activation_rate_pct;

-- name: q01_dau
-- Daily Active Users: distinct user_id with >= 1 event on the calendar day.
-- Calendar is generated so zero-activity days appear. dau_7d_avg = trailing 7-day mean.
WITH RECURSIVE p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
cal(d) AS (SELECT d0 FROM p UNION ALL SELECT date(d, '+1 day') FROM cal, p WHERE d < p.d1),
daily AS (SELECT date(event_timestamp) AS d, COUNT(DISTINCT user_id) AS dau,
                 COUNT(DISTINCT account_id) AS active_accounts, COUNT(*) AS events
          FROM events GROUP BY 1)
SELECT c.d AS activity_date,
       CASE CAST(strftime('%w', c.d) AS INTEGER)
            WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue' WHEN 3 THEN 'Wed'
            WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' ELSE 'Sat' END AS weekday,
       COALESCE(dl.dau, 0)             AS dau,
       COALESCE(dl.active_accounts, 0) AS active_accounts,
       COALESCE(dl.events, 0)          AS events,
       ROUND(AVG(COALESCE(dl.dau, 0)) OVER (ORDER BY c.d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1)
                                       AS dau_7d_avg
FROM cal c LEFT JOIN daily dl ON dl.d = c.d
ORDER BY c.d;

-- name: q02_mau
-- Monthly Active Users: distinct user_id with >= 1 event in the calendar month.
-- pct_of_users_existing_by_month_end: denominator = users with created_at <= end of that month.
WITH mau AS (
  SELECT strftime('%Y-%m', event_timestamp) AS month, COUNT(DISTINCT user_id) AS mau,
         COUNT(DISTINCT account_id) AS active_accounts
  FROM events GROUP BY 1)
SELECT m.month, m.mau, m.active_accounts,
       (SELECT COUNT(*) FROM users u WHERE date(u.created_at) <= date(m.month || '-01', '+1 month', '-1 day'))
                                                              AS users_existing_by_month_end,
       ROUND(100.0 * m.mau /
         (SELECT COUNT(*) FROM users u WHERE date(u.created_at) <= date(m.month || '-01', '+1 month', '-1 day')), 1)
                                                              AS pct_of_users_existing_by_month_end
FROM mau m ORDER BY m.month;

-- name: q03_dau_mau_ratio
-- DAU/MAU "stickiness" per calendar month = (sum of daily DAU / calendar days in month) / MAU.
-- Zero-activity days count as DAU = 0 in the numerator.
WITH RECURSIVE p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
cal(d) AS (SELECT d0 FROM p UNION ALL SELECT date(d, '+1 day') FROM cal, p WHERE d < p.d1),
daily AS (SELECT date(event_timestamp) AS d, COUNT(DISTINCT user_id) AS dau FROM events GROUP BY 1),
m_dau AS (SELECT strftime('%Y-%m', c.d) AS month, COUNT(*) AS days_in_month,
                 SUM(COALESCE(dl.dau, 0)) * 1.0 / COUNT(*) AS avg_dau
          FROM cal c LEFT JOIN daily dl ON dl.d = c.d GROUP BY 1),
m_mau AS (SELECT strftime('%Y-%m', event_timestamp) AS month, COUNT(DISTINCT user_id) AS mau
          FROM events GROUP BY 1)
SELECT d.month, d.days_in_month, ROUND(d.avg_dau, 1) AS avg_dau, m.mau,
       ROUND(d.avg_dau / m.mau, 4) AS dau_mau_ratio
FROM m_dau d JOIN m_mau m ON m.month = d.month ORDER BY d.month;

-- name: q04_activation_rate
-- Account activation (account-level). Cohort = accounts that signed up inside the window with at
-- least 14 full days of observation (signup_date <= window_end - 13 days). An account is ACTIVATED
-- if, within its first 14 days (signup_date .. signup_date+13), >= 2 distinct users fired events
-- AND >= 3 distinct CRM features were used. Denominator = cohort accounts (activated or not).
WITH p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
act AS (
  SELECT a.account_id, a.subscription_plan, a.industry, a.company_size,
         COUNT(DISTINCT e.user_id) AS early_users,
         COUNT(DISTINCT e.feature_name) AS early_features,
         CASE WHEN COUNT(DISTINCT e.user_id) >= 2 AND COUNT(DISTINCT e.feature_name) >= 3
              THEN 1 ELSE 0 END AS activated
  FROM accounts a CROSS JOIN p
  LEFT JOIN events e ON e.account_id = a.account_id
       AND date(e.event_timestamp) >= a.signup_date
       AND date(e.event_timestamp) < date(a.signup_date, '+14 days')
  WHERE a.signup_date BETWEEN p.d0 AND date(p.d1, '-13 days')
  GROUP BY a.account_id, a.subscription_plan, a.industry, a.company_size)
SELECT 'All' AS dimension, 'All cohort accounts' AS segment, COUNT(*) AS cohort_accounts,
       SUM(activated) AS activated_accounts, ROUND(100.0 * SUM(activated) / COUNT(*), 1) AS activation_rate_pct
FROM act
UNION ALL
SELECT 'Plan', subscription_plan, COUNT(*), SUM(activated), ROUND(100.0 * SUM(activated) / COUNT(*), 1)
FROM act GROUP BY subscription_plan
UNION ALL
SELECT 'Company size', company_size, COUNT(*), SUM(activated), ROUND(100.0 * SUM(activated) / COUNT(*), 1)
FROM act GROUP BY company_size
UNION ALL
SELECT 'Industry', industry, COUNT(*), SUM(activated), ROUND(100.0 * SUM(activated) / COUNT(*), 1)
FROM act GROUP BY industry;

-- name: q05_feature_adoption
-- Feature adoption over the 90-day window, at two levels:
--   account-level: account has >= 1 event on the feature; denominators = ACTIVE accounts (>= 1 event
--                  of any kind) and, for reference, ALL accounts.
--   user-level:    user has >= 1 event on the feature; denominator = ACTIVE users (>= 1 event of any kind).
WITH feats(feature_name) AS (VALUES ('Lead Management'), ('Contact Management'), ('Deal Pipeline'),
                                    ('Workflow Automation'), ('Reporting'), ('Email Integration')),
base AS (SELECT (SELECT COUNT(*) FROM accounts)               AS all_accounts,
                (SELECT COUNT(DISTINCT account_id) FROM events) AS active_accounts,
                (SELECT COUNT(DISTINCT user_id) FROM events)    AS active_users),
fa AS (SELECT feature_name, COUNT(DISTINCT account_id) AS accounts_using, COUNT(DISTINCT user_id) AS users_using
       FROM events GROUP BY feature_name)
SELECT f.feature_name,
       COALESCE(fa.accounts_using, 0) AS accounts_using,
       b.active_accounts,
       ROUND(100.0 * COALESCE(fa.accounts_using, 0) / b.active_accounts, 1) AS account_adoption_pct_of_active_accounts,
       b.all_accounts,
       ROUND(100.0 * COALESCE(fa.accounts_using, 0) / b.all_accounts, 1)    AS account_adoption_pct_of_all_accounts,
       COALESCE(fa.users_using, 0) AS users_using,
       b.active_users,
       ROUND(100.0 * COALESCE(fa.users_using, 0) / b.active_users, 1)       AS user_adoption_pct_of_active_users
FROM feats f CROSS JOIN base b LEFT JOIN fa ON fa.feature_name = f.feature_name
ORDER BY account_adoption_pct_of_active_accounts DESC;

-- name: q06_feature_usage_frequency
-- Usage intensity per feature: events, share of all events, and events per adopting user / account.
-- events_per_using_user = feature events / distinct users with >= 1 event on that feature.
SELECT feature_name,
       COUNT(*) AS events,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM events), 1) AS pct_of_all_events,
       COUNT(DISTINCT user_id)    AS users_using,
       COUNT(DISTINCT account_id) AS accounts_using,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT user_id), 1)    AS events_per_using_user,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT account_id), 1) AS events_per_using_account,
       COUNT(DISTINCT date(event_timestamp) || user_id)      AS user_active_days,
       ROUND(1.0 * COUNT(DISTINCT date(event_timestamp) || user_id) / COUNT(DISTINCT user_id), 2)
                                                             AS active_days_per_using_user
FROM events GROUP BY feature_name ORDER BY events DESC;

-- name: q07_new_vs_established
-- Feature adoption in a fixed 30-day exposure window so accounts with different tenure are compared fairly.
--   New         = signed up inside the window with 30 full days observed (signup_date <= window_end - 29 days);
--                 exposure = signup_date .. signup_date+29.
--   Established = signed up before the window; exposure = first 30 days of the window (Jan 1 .. Jan 30).
-- Denominator per cohort = accounts with >= 1 event of any kind in their exposure window.
WITH feats(feature_name) AS (VALUES ('Lead Management'), ('Contact Management'), ('Deal Pipeline'),
                                    ('Workflow Automation'), ('Reporting'), ('Email Integration')),
p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
elig AS (
  SELECT a.account_id,
         CASE WHEN a.signup_date >= p.d0 THEN 'New (signed up in window)'
              ELSE 'Established (signed up before window)' END AS cohort,
         CASE WHEN a.signup_date >= p.d0 THEN a.signup_date ELSE p.d0 END AS exp_start
  FROM accounts a CROSS JOIN p
  WHERE a.signup_date < p.d0 OR a.signup_date <= date(p.d1, '-29 days')),
ex AS (
  SELECT DISTINCT el.account_id, el.cohort, e.feature_name
  FROM elig el JOIN events e ON e.account_id = el.account_id
       AND date(e.event_timestamp) >= el.exp_start
       AND date(e.event_timestamp) <  date(el.exp_start, '+30 days')),
elig_n AS (SELECT cohort, COUNT(*) AS eligible_accounts FROM elig GROUP BY cohort),
base AS (SELECT cohort, COUNT(DISTINCT account_id) AS active_accounts FROM ex GROUP BY cohort),
ad AS (SELECT cohort, feature_name, COUNT(*) AS adopting FROM ex GROUP BY cohort, feature_name)
SELECT b.cohort, en.eligible_accounts, b.active_accounts, f.feature_name,
       COALESCE(ad.adopting, 0) AS adopting_accounts,
       ROUND(100.0 * COALESCE(ad.adopting, 0) / b.active_accounts, 1) AS adoption_pct_of_active_accounts
FROM base b JOIN elig_n en ON en.cohort = b.cohort
CROSS JOIN feats f LEFT JOIN ad ON ad.cohort = b.cohort AND ad.feature_name = f.feature_name
ORDER BY f.feature_name, b.cohort;

-- name: q08_engagement_by_plan
-- Engagement by current subscription plan (accounts.subscription_plan). Window = 90 days.
--   pct_accounts_active  = accounts with >= 1 event / all accounts in plan
--   pct_users_active     = active users / all users in plan
--   events_per_account_30d = events / account-exposure-days * 30 (normalises mid-window signups)
SELECT subscription_plan AS segment,
       COUNT(*) AS accounts,
       SUM(events > 0) AS active_accounts,
       ROUND(100.0 * SUM(events > 0) / COUNT(*), 1) AS pct_accounts_active,
       SUM(n_users) AS total_users,
       SUM(active_users) AS active_users,
       ROUND(100.0 * SUM(active_users) / SUM(n_users), 1) AS pct_users_active,
       SUM(events) AS events,
       ROUND(1.0 * SUM(events) / COUNT(*), 1) AS events_per_account,
       ROUND(30.0 * SUM(events) / SUM(exposure_days), 2) AS events_per_account_30d,
       ROUND(1.0 * SUM(events) / SUM(active_users), 1) AS events_per_active_user,
       ROUND(AVG(CASE WHEN events > 0 THEN features_used END), 2) AS avg_features_per_active_account
FROM v_account_stats GROUP BY subscription_plan
ORDER BY CASE subscription_plan WHEN 'Starter' THEN 1 WHEN 'Professional' THEN 2 ELSE 3 END;

-- name: q08b_feature_by_plan
-- Feature usage by current plan. adoption denominator = ACTIVE accounts in that plan;
-- pct_of_plan_events denominator = all events from accounts in that plan.
WITH feats(feature_name) AS (VALUES ('Lead Management'), ('Contact Management'), ('Deal Pipeline'),
                                    ('Workflow Automation'), ('Reporting'), ('Email Integration')),
plans AS (SELECT subscription_plan AS plan, SUM(events > 0) AS active_accounts, SUM(events) AS plan_events
          FROM v_account_stats GROUP BY subscription_plan),
fp AS (SELECT a.subscription_plan AS plan, e.feature_name, COUNT(DISTINCT e.account_id) AS adopting_accounts,
              COUNT(*) AS events
       FROM events e JOIN accounts a ON a.account_id = e.account_id GROUP BY 1, 2)
SELECT pl.plan, f.feature_name, pl.active_accounts, COALESCE(fp.adopting_accounts, 0) AS adopting_accounts,
       ROUND(100.0 * COALESCE(fp.adopting_accounts, 0) / pl.active_accounts, 1) AS adoption_pct_of_active_accounts,
       COALESCE(fp.events, 0) AS events,
       ROUND(100.0 * COALESCE(fp.events, 0) / pl.plan_events, 1) AS pct_of_plan_events
FROM plans pl CROSS JOIN feats f LEFT JOIN fp ON fp.plan = pl.plan AND fp.feature_name = f.feature_name
ORDER BY CASE pl.plan WHEN 'Starter' THEN 1 WHEN 'Professional' THEN 2 ELSE 3 END, f.feature_name;

-- name: q09_engagement_by_industry
-- Same metric definitions as q08, grouped by industry. Sorted by events_per_account_30d (low first).
SELECT industry AS segment,
       COUNT(*) AS accounts,
       SUM(events > 0) AS active_accounts,
       ROUND(100.0 * SUM(events > 0) / COUNT(*), 1) AS pct_accounts_active,
       SUM(n_users) AS total_users,
       SUM(active_users) AS active_users,
       ROUND(100.0 * SUM(active_users) / SUM(n_users), 1) AS pct_users_active,
       SUM(events) AS events,
       ROUND(1.0 * SUM(events) / COUNT(*), 1) AS events_per_account,
       ROUND(30.0 * SUM(events) / SUM(exposure_days), 2) AS events_per_account_30d,
       ROUND(1.0 * SUM(events) / SUM(active_users), 1) AS events_per_active_user,
       ROUND(AVG(CASE WHEN events > 0 THEN features_used END), 2) AS avg_features_per_active_account
FROM v_account_stats GROUP BY industry ORDER BY events_per_account_30d;

-- name: q09b_engagement_by_company_size
-- Same metric definitions as q08, grouped by company size.
SELECT company_size AS segment,
       COUNT(*) AS accounts,
       SUM(events > 0) AS active_accounts,
       ROUND(100.0 * SUM(events > 0) / COUNT(*), 1) AS pct_accounts_active,
       SUM(n_users) AS total_users,
       SUM(active_users) AS active_users,
       ROUND(100.0 * SUM(active_users) / SUM(n_users), 1) AS pct_users_active,
       SUM(events) AS events,
       ROUND(1.0 * SUM(events) / COUNT(*), 1) AS events_per_account,
       ROUND(30.0 * SUM(events) / SUM(exposure_days), 2) AS events_per_account_30d,
       ROUND(1.0 * SUM(events) / SUM(active_users), 1) AS events_per_active_user,
       ROUND(AVG(CASE WHEN events > 0 THEN features_used END), 2) AS avg_features_per_active_account
FROM v_account_stats GROUP BY company_size
ORDER BY CASE company_size WHEN '1-10' THEN 1 WHEN '11-50' THEN 2 WHEN '51-200' THEN 3 ELSE 4 END;

-- name: q10_inactive_accounts
-- Inactive account = eligible account (signup_date <= window_end - 29 days, i.e. >= 30 days of history in
-- the window) with NO events in the last 30 days of the window (window_end-29 .. window_end).
-- inactivity_type separates accounts never seen in the window from accounts that lapsed.
WITH p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params)
SELECT s.account_id, s.signup_date, s.subscription_plan, s.industry, s.company_size, s.region,
       s.n_users, s.events AS events_in_window, s.last_event_date,
       CASE WHEN s.events = 0 THEN 'Never active in window'
            ELSE 'Lapsed (active earlier, none in last 30 days)' END AS inactivity_type,
       (SELECT sb.subscription_status FROM subscriptions sb WHERE sb.account_id = s.account_id
        ORDER BY sb.subscription_start DESC LIMIT 1) AS latest_subscription_status
FROM v_account_stats s CROSS JOIN p
WHERE s.signup_date <= date(p.d1, '-29 days')
  AND NOT EXISTS (SELECT 1 FROM events e WHERE e.account_id = s.account_id
                  AND date(e.event_timestamp) >= date(p.d1, '-29 days'))
ORDER BY s.subscription_plan, s.account_id;

-- name: q10b_inactive_summary
-- Share of eligible accounts that are inactive (denominator = eligible accounts in the segment).
WITH p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
el AS (
  SELECT s.*, CASE WHEN NOT EXISTS (SELECT 1 FROM events e WHERE e.account_id = s.account_id
                    AND date(e.event_timestamp) >= date(p.d1, '-29 days')) THEN 1 ELSE 0 END AS inactive,
         CASE WHEN s.events = 0 THEN 1 ELSE 0 END AS never_active
  FROM v_account_stats s CROSS JOIN p WHERE s.signup_date <= date(p.d1, '-29 days'))
SELECT 'All' AS dimension, 'All eligible accounts' AS segment, COUNT(*) AS eligible_accounts,
       SUM(inactive) AS inactive_accounts, SUM(never_active) AS never_active_accounts,
       ROUND(100.0 * SUM(inactive) / COUNT(*), 1) AS inactive_pct_of_eligible FROM el
UNION ALL
SELECT 'Plan', subscription_plan, COUNT(*), SUM(inactive), SUM(never_active), ROUND(100.0 * SUM(inactive) / COUNT(*), 1)
FROM el GROUP BY subscription_plan
UNION ALL
SELECT 'Company size', company_size, COUNT(*), SUM(inactive), SUM(never_active), ROUND(100.0 * SUM(inactive) / COUNT(*), 1)
FROM el GROUP BY company_size
UNION ALL
SELECT 'Industry', industry, COUNT(*), SUM(inactive), SUM(never_active), ROUND(100.0 * SUM(inactive) / COUNT(*), 1)
FROM el GROUP BY industry;

-- name: q11_new_user_automation
-- Are newly onboarded users adopting Workflow Automation? User-level, 14-day exposure.
--   New users         = created_at inside the window with 14 full days observed (created date <= window_end - 13);
--                       exposure = created date .. +13 days.
--   Established users = created before the window; exposure = Jan 1 .. Jan 14 (reference group).
-- Denominators: pct_of_all_cohort_users uses every user in the cohort; pct_of_active_users uses only users
-- with >= 1 event during their exposure.
WITH p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
cohort AS (
  SELECT u.user_id, u.user_role, a.subscription_plan,
         CASE WHEN date(u.created_at) >= p.d0 THEN 'New users (created in window)'
              ELSE 'Established users (created before window)' END AS cohort,
         CASE WHEN date(u.created_at) >= p.d0 THEN date(u.created_at) ELSE p.d0 END AS exp_start
  FROM users u JOIN accounts a ON a.account_id = u.account_id CROSS JOIN p
  WHERE date(u.created_at) < p.d0 OR date(u.created_at) <= date(p.d1, '-13 days')),
uf AS (
  SELECT c.user_id, c.user_role, c.subscription_plan, c.cohort,
         COUNT(e.event_id) AS events,
         COALESCE(MAX(e.feature_name = 'Workflow Automation'), 0) AS used_automation
  FROM cohort c LEFT JOIN events e ON e.user_id = c.user_id
       AND date(e.event_timestamp) >= c.exp_start
       AND date(e.event_timestamp) <  date(c.exp_start, '+14 days')
  GROUP BY c.user_id, c.user_role, c.subscription_plan, c.cohort)
SELECT cohort, 'All' AS dimension, 'All users' AS segment, COUNT(*) AS cohort_users,
       SUM(events > 0) AS active_users, SUM(used_automation) AS automation_users,
       ROUND(100.0 * SUM(used_automation) / COUNT(*), 1) AS pct_of_all_cohort_users,
       ROUND(100.0 * SUM(used_automation) / NULLIF(SUM(events > 0), 0), 1) AS pct_of_active_users
FROM uf GROUP BY cohort
UNION ALL
SELECT cohort, 'Plan', subscription_plan, COUNT(*), SUM(events > 0), SUM(used_automation),
       ROUND(100.0 * SUM(used_automation) / COUNT(*), 1),
       ROUND(100.0 * SUM(used_automation) / NULLIF(SUM(events > 0), 0), 1)
FROM uf GROUP BY cohort, subscription_plan
UNION ALL
SELECT cohort, 'Role', user_role, COUNT(*), SUM(events > 0), SUM(used_automation),
       ROUND(100.0 * SUM(used_automation) / COUNT(*), 1),
       ROUND(100.0 * SUM(used_automation) / NULLIF(SUM(events > 0), 0), 1)
FROM uf GROUP BY cohort, user_role
ORDER BY cohort DESC, dimension, segment;

-- name: q11b_new_user_feature_adoption
-- Same 14-day exposure and cohorts as q11, but every feature: users with >= 1 event on the feature in their
-- exposure / ACTIVE users in the cohort (>= 1 event in exposure).
WITH feats(feature_name) AS (VALUES ('Lead Management'), ('Contact Management'), ('Deal Pipeline'),
                                    ('Workflow Automation'), ('Reporting'), ('Email Integration')),
p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
cohort AS (
  SELECT u.user_id,
         CASE WHEN date(u.created_at) >= p.d0 THEN 'New users (created in window)'
              ELSE 'Established users (created before window)' END AS cohort,
         CASE WHEN date(u.created_at) >= p.d0 THEN date(u.created_at) ELSE p.d0 END AS exp_start
  FROM users u CROSS JOIN p
  WHERE date(u.created_at) < p.d0 OR date(u.created_at) <= date(p.d1, '-13 days')),
ex AS (
  SELECT DISTINCT c.user_id, c.cohort, e.feature_name
  FROM cohort c JOIN events e ON e.user_id = c.user_id
       AND date(e.event_timestamp) >= c.exp_start
       AND date(e.event_timestamp) <  date(c.exp_start, '+14 days')),
base AS (SELECT cohort, COUNT(DISTINCT user_id) AS active_users FROM ex GROUP BY cohort),
ad AS (SELECT cohort, feature_name, COUNT(*) AS users_using FROM ex GROUP BY cohort, feature_name)
SELECT b.cohort, f.feature_name, b.active_users, COALESCE(ad.users_using, 0) AS users_using,
       ROUND(100.0 * COALESCE(ad.users_using, 0) / b.active_users, 1) AS adoption_pct_of_active_users
FROM base b CROSS JOIN feats f LEFT JOIN ad ON ad.cohort = b.cohort AND ad.feature_name = f.feature_name
ORDER BY b.cohort DESC, f.feature_name;

-- name: model_dim_accounts
-- Power BI account dimension: raw account attributes + derived flags (all computed from the definitions above).
WITH p AS (SELECT obs_start AS d0, obs_end AS d1 FROM analysis_params),
act AS (
  SELECT a.account_id,
         CASE WHEN COUNT(DISTINCT e.user_id) >= 2 AND COUNT(DISTINCT e.feature_name) >= 3 THEN 1 ELSE 0 END AS activated
  FROM accounts a CROSS JOIN p
  LEFT JOIN events e ON e.account_id = a.account_id
       AND date(e.event_timestamp) >= a.signup_date
       AND date(e.event_timestamp) < date(a.signup_date, '+14 days')
  WHERE a.signup_date BETWEEN p.d0 AND date(p.d1, '-13 days')
  GROUP BY a.account_id)
SELECT s.account_id, s.signup_date, s.industry, s.company_size, s.subscription_plan, s.region,
       CASE WHEN s.signup_date >= p.d0 THEN 'New' ELSE 'Established' END AS account_cohort,
       s.n_users, s.events AS events_90d, s.active_users AS active_users_90d, s.features_used AS features_used_90d,
       s.active_days AS active_days_90d, s.last_event_date,
       CASE WHEN s.events > 0 THEN 1 ELSE 0 END AS is_active_90d,
       CASE WHEN act.account_id IS NOT NULL THEN 1 ELSE 0 END AS is_activation_cohort,
       COALESCE(act.activated, 0) AS is_activated,
       CASE WHEN s.signup_date <= date(p.d1, '-29 days') THEN 1 ELSE 0 END AS is_inactive_eligible,
       CASE WHEN s.signup_date <= date(p.d1, '-29 days') AND NOT EXISTS
            (SELECT 1 FROM events e WHERE e.account_id = s.account_id AND date(e.event_timestamp) >= date(p.d1, '-29 days'))
            THEN 1 ELSE 0 END AS is_inactive_last30d,
       (SELECT sb.subscription_status FROM subscriptions sb WHERE sb.account_id = s.account_id
        ORDER BY sb.subscription_start DESC LIMIT 1) AS latest_subscription_status
FROM v_account_stats s CROSS JOIN p LEFT JOIN act ON act.account_id = s.account_id
ORDER BY s.account_id;

-- name: model_dim_users
-- Power BI user dimension.
WITH p AS (SELECT obs_start AS d0 FROM analysis_params)
SELECT u.user_id, u.account_id, u.created_at, date(u.created_at) AS created_date, u.user_role,
       CASE WHEN date(u.created_at) >= p.d0 THEN 'New (created in window)' ELSE 'Established' END AS user_cohort
FROM users u CROSS JOIN p ORDER BY u.user_id;

-- name: model_fact_events
-- Power BI fact table: one row per product event, with a date key for the date dimension.
SELECT event_id, user_id, account_id, event_timestamp, date(event_timestamp) AS event_date,
       event_name, feature_name, session_id
FROM events ORDER BY event_id;
