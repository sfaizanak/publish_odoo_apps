# POS Cashier Risk Monitor - pos_cashier_risk_monitor

Odoo 19 addon for explainable POS cashier-risk monitoring, implemented incrementally from the PRD.

## Current status

Phases 0 through 15 are implemented:

- Phase 2: configurable rules, settings, seed rules, validation, and security.
- Phase 3: risk cases, reasons, workflow, chatter, activities, and access rules.
- Phase 4: POS order analysis state, risk scores/levels, case count, timestamps,
  failure text, smart button, and administrator analysis/retry actions.
- Phase 5: POS OWL event capture for manual price overrides and line deletion,
  offline-persisted event payloads, backend reconciliation, UUID idempotency,
  and validated event ownership/context.
- Phase 6: normalized order, line, event, discount, margin, override, refund,
  deletion, cancellation, and financial-exposure feature extraction.
- Phase 7: safe deterministic rule evaluation using the configured operator,
  scope, threshold, minimum amount, company, and POS configuration filters.
- Phase 8: weighted risk scoring, risk-level classification, explainable case
  creation/update, reason records, duplicate prevention, and automatic analysis
  after POS order synchronization.
- Phase 9: configurable manager notifications and idempotent activities for high and
  critical cases.
- Phase 10: cashier/POS/company behavioural baselines with nightly recalculation and
  cashier-to-company fallback selection.
- Phase 11: baseline-aware hybrid scoring and statistical explanations.
- Phase 12: risk-case list, graph, pivot and reporting filters.
- Phase 13: optional per-POS Isolation Forest models, metadata, feature deviations,
  scheduled retraining and deterministic fallback when scikit-learn is unavailable.
- Phase 14: ten demo/evaluation scenarios with linked-order evaluation and precision,
  false-alert, acceptance-rate and exposure metrics.
- Phase 15: security hardening, multi-company rules, bounded cron processing,
  regression tests, store documentation and release packaging guidance.

## Installation

Install the module from Apps after updating the Apps list. Enable monitoring per POS
configuration. Scikit-learn is optional: install the pinned range in
`requirements.txt` only when Isolation Forest is required. The module continues to
provide rules and baselines without it.

For a demonstration, enable demo data while installing. Open Risk Monitoring >
Evaluation Runs, link completed POS orders to the ten scenarios, and click Evaluate
Scenarios. The metrics are a review aid, not a claim of fraud detection accuracy.

## Security and privacy

Cashiers do not receive risk-case access by default. Monitoring users see assigned
cases; managers see cases in allowed companies; administrators configure rules and
models. All company-sensitive records have company restrictions. Event metadata is
intended for operational values only and must not contain payment or personal data.

## Verification

Python compilation, JavaScript syntax checking, XML parsing, module upgrade, and the
tagged addon test suite pass in the local Odoo 19 environment. The release package
must contain only this addon directory, exclude `__pycache__`, `.pyc`, `.git`, local
configuration and research notes, and be validated by installing/upgrading it on a
clean Odoo 19 database.
