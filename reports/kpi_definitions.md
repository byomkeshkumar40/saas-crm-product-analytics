# KPI Definitions

Observation window: **2026-01-01 → 2026-03-31 (90 days = Jan 31 + Feb 28 + Mar 31)**. All dates are calendar days
derived from `events.event_timestamp`. "Active" always means **≥ 1 event**. SQL query IDs refer to
`sql/product_analysis.sql`; results are in `data/processed/kpi_tables/<query>.csv`.

| KPI | Level | Definition | Numerator | Denominator | Query |
|---|---|---|---|---|---|
| Daily Active Users (DAU) | user | Distinct `user_id` with ≥ 1 event on a calendar day | – | – | q01 |
| Avg DAU | user | Mean DAU over all 90 calendar days (zero-activity days count as 0) | Σ daily DAU | 90 days | q00 |
| Monthly Active Users (MAU) | user | Distinct `user_id` with ≥ 1 event in a calendar month | – | – | q02 |
| DAU/MAU ratio | user | Avg DAU in the month ÷ MAU of the same month | avg DAU in month | MAU in month | q03 |
| Active users (90 d) | user | Distinct users with ≥ 1 event in the window | – | – | q00 |
| Active-user share | user | Active users ÷ all users in `users` | active users | all 6,331 users | q00 |
| Activation rate | account | Of accounts that signed up in the window with ≥ 14 observed days (`signup_date ≤ 2026-03-18`), share that in their first 14 days (signup day + 13) had events from **≥ 2 distinct users** and **≥ 3 distinct features** | activated cohort accounts | cohort accounts | q04 |
| Account adoption of a feature | account | Accounts with ≥ 1 event on the feature in the window ÷ **active** accounts (≥ 1 event of any kind). Also reported against all accounts | accounts using feature | active accounts (primary); all accounts (reference) | q05 |
| User adoption of a feature | user | Users with ≥ 1 event on the feature ÷ **active** users | users using feature | active users | q05 |
| Feature usage frequency | event | Events per feature, share of all events, events per adopting user/account, active days per adopting user | – | – | q06 |
| New vs established adoption | account | Account adoption in a fixed **30-day exposure**: New = signed up in window with 30 observed days (`signup_date ≤ 2026-03-02`, exposure signup→+29); Established = signed up before window (exposure Jan 1–Jan 30). Denominator = accounts of that cohort with ≥ 1 event in their exposure | accounts using feature | cohort accounts active in exposure | q07 |
| Pct accounts active (segment) | account | Accounts with ≥ 1 event in window ÷ all accounts in segment | active accounts | segment accounts | q08/q09 |
| Pct users active (segment) | user | Active users ÷ all users of segment accounts | active users | segment users | q08/q09 |
| Events per account / 30 d | account | Events ÷ account-exposure-days × 30; exposure = days the account existed inside the window (normalises mid-window signups) | events | Σ exposure days | q08/q09 |
| Events per active user | user | Events ÷ active users | events | active users | q08/q09 |
| Inactive account | account | Account with `signup_date ≤ 2026-03-02` (≥ 30 days of history) and **no events in the last 30 days** (2026-03-02 → 2026-03-31). *Never active* = no events at all in the window; *Lapsed* = events earlier only | inactive accounts | eligible accounts (signup ≤ 2026-03-02) | q10/q10b |
| New-user automation adoption | user | Users with ≥ 1 `Workflow Automation` event in their first 14 days (created-date → +13). New users: created in window with ≥ 14 observed days (created ≤ 2026-03-18). Reference: established users, exposure Jan 1–14 | automation users | all cohort users (and, separately, active cohort users) | q11/q11b |

## Notes on interpretation
* **User-level vs account-level.** An account "adopts" a feature if *any* of its users used it; a user adopts only
  by their own events. Account-level adoption is therefore always ≥ user-level adoption of the same feature.
* **Plan** is the *current* plan in `accounts.subscription_plan` (matches the latest `subscriptions` row);
  upgrades that happened inside the window are attributed to the current plan for all events.
* **Company size is correlated with plan** in this dataset (small companies are mostly Starter), so plan and
  size effects cannot be separated by these tables alone.
* **DAU/MAU** counts users who exist in the denominator MAU only if they were active that month; the user base
  grows during the window as new users are created.
* **Exposure differences.** 90-day totals favour accounts that existed longer; this is why q07 uses fixed-length
  windows and q08/q09 report `events_per_account_30d`.
