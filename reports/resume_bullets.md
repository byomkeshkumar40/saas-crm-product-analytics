# Resume bullets (all figures from this project's validated outputs; data is synthetic)

- Built a reproducible synthetic B2B SaaS CRM dataset (1,200 accounts, 6,331 users, 76,207 events, 90-day window) with seeded Python and a SQLite database, plus a 68-check validation suite (unique IDs, foreign keys, timestamps, KPI recomputation) that passes.
- Wrote SQLite queries (CTEs, window functions) defining DAU/MAU, 14-day account activation, and account- vs user-level feature adoption with explicit denominators; on the synthetic data, activation was 37.7% (103/273 accounts) and DAU/MAU averaged about 0.08.
- Analyzed segment engagement in the synthetic data: Workflow Automation reached 8.0% of new vs 25.9% of established accounts (30-day window), and 36.1% of Starter accounts were inactive vs 13.1% for Enterprise; delivered Power BI-ready tables and DAX measures (no .pbix built) and prioritized onboarding recommendations.
