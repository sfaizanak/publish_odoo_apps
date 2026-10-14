# Release notes — 19.0.2.0.0

This release completes the PRD demo/evaluation and hardening work.

## Phase 14

- Adds ten documented evaluation scenarios covering ordinary sales, discounts,
  price overrides, below-cost sales, deletions, linked/unlinked refunds, repeated
  refunds, baseline anomalies and valid exceptions.
- Allows a manager to link scenarios to real completed POS orders.
- Calculates precision, false alerts per 1,000 evaluated orders, acceptance rate,
  confusion-matrix counts and observed case exposure.
- Keeps scenario evaluation separate from production scoring; it never changes a
  POS order or automatically labels cashier behaviour as fraud.

## Phase 15

- Adds explicit company record rules and access rights for evaluation records.
- Adds regression coverage for demo scenario integrity and empty-run metrics.
- Adds store-facing documentation and optional-ML installation guidance.
- Keeps Isolation Forest optional. The module remains usable with rules and
  behavioural baselines if scikit-learn is not installed.

## Store upload checklist

1. Upload the contents of the `pos_cashier_risk_monitor` directory as one module.
2. Use Odoo 19.0 and LGPL-3 as the compatibility/license values.
3. Install first with demo data on a clean database and run the tagged test suite.
4. Review the security groups with a cashier, monitoring user, manager and admin.
5. If ML is required, install the version range in `requirements.txt` before
   enabling Isolation Forest; otherwise leave that option disabled.
6. Do not upload `.git`, `__pycache__`, `.pyc`, local configuration, logs or the
   parent repository.
