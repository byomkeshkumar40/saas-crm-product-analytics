# Product Insights – SaaS CRM Usage & Feature Adoption

**Data:** synthetic (seed 42): 1,200 accounts, 6,331 users, 76,207 events, 2026-01-01 → 2026-03-31.
Every number below comes from `data/processed/kpi_tables/` (SQL in `sql/product_analysis.sql`) and was
reconciled by `scripts/validate_data.py`. **Findings** = what the data shows. **Hypotheses** = possible
causes that this data cannot prove. Because the data is synthetic and I wrote the generator, plan, tenure and
role effects were built in – the findings demonstrate the analysis method, not real-world customer behaviour.

## Headline KPIs
| KPI | Value | Source |
|---|---|---|
| Total accounts / users | 1,200 / 6,331 | q00 |
| Active accounts (90 d) | 1,059 (88.3% of accounts) | q00 |
| Active users (90 d) | 3,575 (56.5% of users) | q00 |
| Avg DAU / MAU (March) | 169.0 / 2,470 | q00 |
| DAU/MAU by month (Jan, Feb, Mar) | 0.075, 0.083, 0.080 | q03 |
| Activation rate | 37.7% (103 of 273 cohort accounts) | q04 |

## Insight 1 – Advanced features are the adoption gap, especially for new accounts
**Findings**
* Account-level adoption (share of 1,059 active accounts): Contact Management 93.4%, Lead Management 89.8%, Deal
  Pipeline 78.0%, Email Integration 55.4%, **Reporting 44.8%, Workflow Automation 26.8%** (q05).
* Workflow Automation is 4.7% of all events and has the lowest intensity (5.3 events per adopting user vs 7.2 for
  Contact Management) (q06).
* Fixed 30-day exposure (q07): Workflow Automation was used by **8.0%** of new accounts (14 of 176) vs **25.9%**
  of established accounts (173 of 667); Reporting 18.8% vs 40.6%. Core features were close (e.g. Contact
  Management 90.9% new vs 87.0% established).
* New users (first 14 days): 3.9% of all new users used automation (86 of 2,232), 8.7% of those who were active
  (86 of 991) (q11). By plan, among active new users: Enterprise 17.1%, Professional 7.2%, **Starter 1.7%**.
* By plan (q08b): Workflow Automation reaches 6.8% of active Starter accounts, 31.6% Professional, 60.1% Enterprise.

**Hypotheses (untested)**
* Automation has a high set-up cost and the value is not visible in the first weeks.
* Starter users may not have access to, or may not be shown, automation (plan gating or discovery).
* Admins are the natural automation owners; new sales reps (2.4% of all new reps) have no reason to build workflows.
  (Finding: among established users the admin role has the highest automation share, 28.3% of active admins, q11.)

**Recommendations**
1. Add a guided "first automation" (templates such as *new lead → assign owner → send email*) to admin onboarding.
2. Surface automation and Reporting in-product at day 7–14, after core records exist.
3. For Starter, test a limited automation preview to see whether discovery or access is the barrier.

**Success metrics:** % of new accounts using Workflow Automation within 30 days (baseline 8.0%); % of new admins
creating a workflow in 14 days; automation events per adopting user (baseline 5.3).

## Insight 2 – Small, Starter-plan accounts are the low-engagement, low-activation segment
**Findings**
* Activation: Enterprise 60.0% (27/45), Professional 42.6% (49/115), **Starter 23.9% (27/113)** (q04). By size:
  1–10 employees 21.2% vs 201+ 68.2% (15/22).
* Inactive accounts (no events in last 30 days, q10b): 285 of 1,083 eligible = 26.3%. **Starter 36.1%** vs
  Enterprise 13.1%; **1–10 employees 41.5%** vs 201+ 9.2%.
* Events per account per 30 days: Starter 12.43, Professional 25.09, Enterprise 52.84 (q08).
* Industry (q09, events per account per 30 days): lowest Manufacturing 17.21, Healthcare 17.64, Education 18.24;
  highest Professional Services 33.82. Manufacturing also has the highest inactive share among industries
  (34.2%, q10b) – but industry differences are smaller than plan/size differences.

**Hypotheses (untested)**
* Small accounts have few users, so a lack of team adoption leaves no one to re-engage the account.
* Starter accounts may be less committed (lower price, lighter onboarding) and churn quietly.
* Plan and size are correlated here, so this data cannot say which one drives the gap.

**Recommendations**
1. Target the inactive accounts with lifecycle outreach (list: `q10_inactive_accounts.csv`). 71 of the 285 already
   have a `cancelled` latest subscription; the other 214 (207 `active`, 7 `past_due`) are still paying-status
   accounts that are silent – start with the 113 never-active accounts.
2. Add a 14-day checklist for Starter accounts: invite a second user, import contacts, log a deal.
3. Run an A/B test of an assisted-onboarding offer for 1–10 employee accounts.

**Success metrics:** activation rate for Starter (baseline 23.9%); inactive share among Starter (36.1%); % of new
accounts with ≥ 2 active users in 14 days.

## Insight 3 – Usage is shallow and weekday-bound: DAU/MAU is ~0.08
**Findings**
* DAU/MAU is 0.075 (Jan), 0.083 (Feb), 0.080 (Mar) (q03): on an average day only about 8% of the month's active
  users are present. For a daily-use sales tool this is low.
* 43.5% of users (2,756 of 6,331) never fired an event in the 90 days (q00: 3,575 active).
* Average weekday DAU is 217.7 vs 49.1 on weekends (computed from q01), consistent with a business tool.
* Overall activation is 37.7% – nearly two of three new accounts do not reach 2 users and 3 features in 14 days (q04).
* 14-day behaviour of new users: 991 of 2,232 (44.4%) were active at all in their first 14 days (q11).

**Hypotheses (untested)**
* Many invited users are never activated (invite fatigue, no clear first task).
* CRM use may be periodic (pipeline reviews) rather than daily; DAU/MAU may be the wrong yardstick and weekly
  active ratio may suit this product better.

**Recommendations**
1. Instrument and improve the invited-user journey (invite → first login → first record).
2. Track weekly-active/monthly-active (WAU/MAU) next to DAU/MAU before setting a stickiness target.
3. Send a first-week "what to do next" prompt based on the user's role.

**Success metrics:** % of invited users active within 14 days (baseline 44.4%); DAU/MAU (baseline 0.08);
activation rate (baseline 37.7%).

## What this analysis does not show
* Causality – no experiments, and the data is synthetic.
* Churn timing and revenue – `subscriptions` has no end date or price.
* Whether low engagement predicts cancellation.
