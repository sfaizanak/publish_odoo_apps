# AGENTS.md - Odoo 19 POS Cashier Risk Monitor

## 0. Source of Truth & Credit Saving Rule
- Main PRD: `./PRD.md` (This is your file `Odoo-19-POS-Risk-Monitor-PRD.md`, rename it to `PRD.md`)
- Rule: Read PRD.md completely ONLY ONCE per new chat session. For subsequent tasks in same session, use cached understanding.
- Do NOT re-read full PRD for every small fix. Implement ONE phase at a time.
- Current Odoo Version is 19 ONLY. Never use Odoo 16/17/18 field names or patch points. Always verify from installed Odoo 19 source.

## 1. Product Definition
- Product: Odoo 19 POS Cashier Risk Monitor
- Technical Addon Name: `pos_cashier_risk_monitor`
- Depends: `["point_of_sale", "mail"]` - DO NOT add `stock`, `hr`, `pos_hr`, `queue_job`, `scikit-learn` until that phase is approved.
- Vision: Detect cashier errors and suspicious POS patterns, assign explainable risk score 0-100, create review cases. System identifies RISK, not fraud. Final decision is always manager's.
- Prohibited Wording: NEVER output "The cashier committed fraud", "This employee is fraudulent", "Fraud confirmed". Use: "Potential fraud-risk activity", "Suspicious transaction requiring review", "Possible cashier error", "Unusual cashier activity".

## 2. Security Groups & Access
- Create XML IDs: `group_pos_risk_user`, `group_pos_risk_manager`, `group_pos_risk_admin`
- Inheritance: Risk Administrator -> Risk Manager -> Risk Monitoring User
- Cashier: NO read access to `pos.risk.case` and `pos.risk.case.reason` by default. No delay in payment flow.
- Monitoring User: View assigned cases, add notes only.
- Manager: View company cases, start/classify/close investigations, create activities.
- Admin: All manager perms + configure rules, thresholds, cron, retrain.
- Requirements: All business models must have `company_id` where appropriate, multi-company record rules using allowed companies, no unrestricted `sudo()`, chatter logging for reviewer actions, cases must be archived not deleted.

## 3. Directory Structure (MUST Follow)
```
pos_cashier_risk_monitor/
├── __manifest__.py
├── models/ pos_order.py, pos_order_line.py, risk_rule.py, risk_event.py, risk_case.py, risk_case_reason.py, cashier_baseline.py, res_config_settings.py
├── services/ feature_extractor.py, rule_engine.py, baseline_engine.py, anomaly_engine.py, risk_calculator.py, explanation_engine.py
├── security/ security.xml, ir.model.access.csv
├── data/ sequence_data.xml, risk_rule_data.xml, cron_data.xml, mail_activity_data.xml
├── views/ risk_rule_views.xml, risk_event_views.xml, risk_case_views.xml, cashier_baseline_views.xml, pos_order_views.xml, res_config_settings_views.xml, menu_views.xml
├── static/src/js/ pos_event_tracker.js
├── tests/ common.py, test_security.py, test_rule_engine.py, test_analysis_job.py, test_case_workflow.py
└── demo/ demo_data.xml
```
Keep algorithms in `services/`, not inside models.

## 4. Core Data Models

### 4.1 pos.order extension
- `risk_analysis_state`: Selection `not_required`, `pending`, `processing`, `completed`, `failed`, indexed, default based on POS config enabled
- `risk_score`: Float 0-100
- `risk_level`: Selection `none`, `low`, `medium`, `high`, `critical`
- `risk_case_count`: Integer computed
- `risk_analyzed_at`: Datetime
- `risk_analysis_error`: Text, admin only
- `risk_case_ids`: One2many to pos.risk.case
- Add smart button when case exists.

### 4.2 pos.order.line extension
- `risk_original_unit_price`: Float - effective pricelist price BEFORE manual intervention, NOT lst_price
- `risk_is_manual_price_override`: Boolean - True only for manual override
- `risk_price_override_difference`: Float
- `risk_price_override_percentage`: Float, handle zero safely
- `risk_price_override_reason`: Char optional
- `risk_manual_price_change_count`: Integer

### 4.3 pos.risk.event (Frontend capture)
- Fields: `name`, `event_uuid` (unique, required), `order_uuid`, `order_id` (Many2one pos.order), `order_line_uuid`, `order_line_id`, `cashier_id` (res.users), `session_id` (pos.session), `config_id` (pos.config), `company_id` (required, indexed), `product_id`, `event_type` (Selection: discount_applied, price_overridden, line_deleted, quantity_changed, refund_started, order_cancelled, payment_cancelled), `old_numeric_value`, `new_numeric_value`, `quantity`, `currency_id`, `event_at` (UTC), `server_received_at`, `reason`, `metadata_json` (Json, no sensitive data), `processed` (Boolean)
- SQL Constraint: unique event_uuid
- Must reject malformed events without crashing order sync. Validate company/cashier backend-side.

### 4.4 pos.risk.rule
- Fields: `name`, `code` (immutable after use, unique per company), `active`, `company_id`, `config_ids` (Many2many pos.config), `category` (discount, price_override, deletion, cancellation, refund, timing, combined), `scope` (order, line, event, cashier_window), `operator` (safe operators only, NEVER safe_eval), `threshold_value`, `secondary_threshold_value`, `window_minutes`, `minimum_amount` (Monetary), `severity_score` (0-100), `risk_weight`, `case_classification`, `description`, `recommended_action`
- Implement explicit evaluator registry keyed by code. No arbitrary Python.

### 4.5 pos.cashier.baseline
- Fields: `cashier_id`, `config_id`, `company_id` (required), `baseline_level` (cashier, pos, company), `period_start`, `period_end`, `sample_count`, `avg_discount_pct`, `std_discount_pct`, `p95_discount_pct`, `avg_price_override_pct`, `std_price_override_pct`, `avg_deleted_lines`, `p95_deleted_lines`, `avg_refund_amount`, `p95_refund_amount`, `refund_frequency`, `calculated_at`
- Fallback: Cashier (sample>=30) -> POS -> Company
- Uniqueness: No 2 baselines for same subject and period.

### 4.6 pos.risk.case
- Fields: `name` (sequence), `active`, `fingerprint` (unique idempotency key: company+order+line/event+category+rule/model version), `company_id`, `order_id` (required), `order_line_id`, `event_ids` (Many2many), `cashier_id`, `session_id`, `config_id`, `category`, `classification` (possible_error, policy_violation, behavioural_anomaly, fraud_risk, requires_review), `rule_score`, `anomaly_score`, `impact_score`, `risk_score` (0-100 final), `risk_level` (low, medium, high, critical), `currency_id`, `financial_exposure` (Monetary), `explanation` (Text/Html sanitized), `recommended_action`, `state` (new -> under_review -> resolved -> closed, allow new->closed only if duplicate), `assigned_user_id`, `reviewed_by`, `reviewed_at`, `review_outcome` (cashier_mistake, policy_violation, training_required, suspicious_activity, configuration_issue, valid_business_operation, false_positive, duplicate), `review_notes`, `detected_at`, `model_version`
- Inherits: `mail.thread`, `mail.activity.mixin`

### 4.7 pos.risk.case.reason
- Fields: `case_id`, `rule_id` (optional), `reason_code`, `description`, `observed_value`, `expected_value`, `deviation_value`, `contribution_score`, `financial_exposure`, `sequence`
- Must be understandable without logs.

## 5. Configuration (res.config.settings)
- Enable POS risk monitoring: False per POS config
- Analyze completed orders automatically: True
- Case-creation threshold: 40, High-risk: 70, Critical: 85
- Minimum cashier baseline sample: 30, Lookback: 90 days
- Create activity for high-risk: True, Notify for critical: True
- Require price-change reason: False
- Weights: rule 0.45, anomaly 0.35, impact 0.20 - Must sum to 1.0 (tolerance allowed)

## 6. Initial Rule Catalogue (Install inactive/conservative)
- HIGH_DISCOUNT: max discount >=25% | sev 60
- NEGATIVE_MARGIN: final price < cost | sev 85
- DRASTIC_PRICE_DECREASE: manual decrease >=30% | sev 75
- DRASTIC_PRICE_INCREASE: manual increase >=30% | sev 55
- EXCESSIVE_LINE_DELETION: >3 deleted lines/order | sev 65
- HIGH_VALUE_LINE_DELETION: deleted value > amount | sev 75
- UNLINKED_REFUND: refund without original line link | sev 90
- HIGH_VALUE_REFUND: refund total > amount | sev 70
- REPEATED_REFUNDS: >=3 refunds in 60 min | sev 80
- COMBINED_OVERRIDE_DELETE: override + deletion | sev 85
- Do NOT hard-code monetary thresholds globally. Per company config.

## 7. Feature Extraction & Scoring
- Feature Extractor must return deterministic dict:
  order_id, company_id, config_id, session_id, cashier_id, order_datetime, order_total, absolute_order_total, line_count, discounted_line_count, max_discount_pct, average_discount_pct, discount_amount, manual_override_count, max_price_deviation_pct, price_override_exposure, deleted_line_count, deleted_line_value, is_refund, refund_amount, refund_line_count, unlinked_refund_line_count, customer_id, hour_of_day, cashier_recent_refund_count, cashier_recent_high_discount_count
- No N+1 queries. Handle zero price, missing customer/cost.
- Scoring: rule_score (0-100), anomaly_score (0-100), impact_score (0-100 normalized exposure). final = rule*0.45 + anomaly*0.35 + impact*0.20. Before anomaly enabled, redistribute weights. Clamp 0-100.
- Exposure: Discount = max(ref - final,0)*qty, Price-decrease = max(orig-final,0)*qty, Refund = abs(refund), Deleted = deleted_price*qty. Never claim exposure = confirmed loss.
- Risk Levels: 0-39.99 Low (save, no case unless configured), 40-69.99 Medium (case), 70-84.99 High (case+activity), 85-100 Critical (priority+notification)

## 8. Explainability
Every case must answer: What happened? Why unusual? Observed vs Expected? Financial exposure? Next action?
Example: "32% discount applied, exceeding 20% threshold. Cashier 90-day avg is 4.6%. Final price below cost. Exposure: 1850. Review authorization."

## 9. Background Processing & Idempotency
- Flow: Order completed -> risk_analysis_state=pending -> Cron every 5 min selects batch (default 100) -> processing -> feature extraction + rules -> scoring -> idempotent case creation -> completed + risk_analyzed_at. On failure: failed + error summary + retry allowed.
- Crons: Analyze pending POS orders (5 min), Recalculate baselines (nightly), Retrain anomaly models (weekly, later phase)
- Fingerprint = company + order + optional line/event + category + rule/model version. Re-run must not duplicate cases/activities.

## 10. UI & Notifications
- Menu: Point of Sale -> Risk Monitoring -> Dashboard, Risk Cases, Cashier Analysis, Behavioural Baselines, Rules, Configuration
- Case List cols: Case number, Detection time, Cashier, POS, POS order, Category, Classification, Financial exposure, Risk score, Risk level, State, Assigned reviewer
- Filters: My assigned, New/under review, High/critical, Cashier, POS, Category, Review outcome, Detection date
- Notifications: High-risk = mail.activity to risk manager (idempotent). Critical = high-priority activity + optional email. Include case ref, order, cashier, score, explanation, exposure, link.

## 11. Baseline Engine (After Phase 8)
- Population: Completed orders, lookback 90 days, exclude cancelled/incomplete, exclude current order being scored
- Stats: mean, std, p95 for discount, override, deletion, refund. z_score = (observed - mean)/std. Handle zero std.
- Resolution: Cashier -> POS -> Company. Record selected baseline and sample size in reason.

## 12. ML Enhancement (Phase 13+, Optional)
- Algorithm: Isolation Forest, unsupervised. One model per company/POS, not per cashier.
- Features: max discount %, discount amount/total, max manual deviation, override count, deleted count, deleted value/total, refund amount, refund line count, unlinked count, order total, line count, hour encoding, cashier recent refund/discount frequency
- Graceful fallback if sklearn not available. Store model metadata: version, period, features, sample, params. Never cross company.

## 13. Incremental Implementation Plan (STRICT)
- Phase 0 - Env Verification: Inspect repo, AGENTS.md, Odoo 19 source, POS fields, test commands. No prod code. Exit: Conventions understood.
- Phase 1 - Scaffold: Manifest, 3 groups, base menu, settings flag, README, smoke test. Acceptance: Installs/upgrades/uninstalls clean. STOP GATE: Do not implement rules/POS patch/ML.
- Phase 2 - Rule Master: pos.risk.rule, settings, views, initial data, admin-only write, validation. Tests: constraints, security, multi-company, archive.
- Phase 3 - Case Workflow: pos.risk.case, reason, sequence, list/form/kanban/search, state methods, chatter. Manual creation admin/test only. Tests: workflow, outcome validation, fingerprint unique, security.
- Phase 4 - POS Backend Extensions: pos.order and pos.order.line fields, smart button, pending marking, Analyze/Retry actions. Tests: enabled vs disabled POS, state transitions, multi-company.
- Phase 5 - Frontend Event Capture: pos.risk.event, pos_event_tracker.js OWL patch, UUID, sync, optional reason prompt. STOP GATE: Verify Odoo 19 patch targets. Tests: JS tests, payload validation, duplicate UUID, offline sync.
- Phase 6 - Feature Extractor: feature_extractor.py service, deterministic, batch efficient. Tests: sales/discount/override/deletion/refund, N+1 check.
- Phase 7 - Rule Engine: Safe registry, initial rules, result contract {triggered, rule_code, category, score, financial_exposure, observed_value, expected_value, reason, recommended_action}, exposure calc, explanation. Tests: positive/negative per rule, disabled rules, scope.
- Phase 8 - Analysis Job & Scoring: 5-min cron, batch 100, score calc, threshold handling, idempotent creation, retry. Tests: e2e, re-run no duplicate, malformed order handling, concurrent. MILESTONE: Complete rule-based product.
- Phase 9 - Notifications: Responsible manager config, high-risk activity, critical email, idempotent.
- Phase 10 - Baselines: pos.cashier.baseline, nightly job, fallback, statistical reasons.
- Phase 11 - Hybrid Score: Anomaly component + weighted formula + explanation.
- Phase 12 - Reporting: Graph, pivot, filters, kanban.
- Phase 13 - Isolation Forest: Optional sklearn, training builder, metadata, scoring service, fallback.
- Phase 14 - Demo Data & Evaluation: 10 scenarios (normal sale, excessive discount, drastic override, below cost, deleted high-value, valid linked refund, unlinked high refund, repeated refunds, unusual for cashier, valid exception). Metrics: precision, false alerts/1000, acceptance %, exposure, avg time.
- Phase 15 - Hardening: Full tests, security review, perf 10k orders, docs.

## 14. Test Strategy
- Unit: Every rule evaluator, score normalization, exposure calc, baseline selection, z-score zero-deviation, fingerprint, workflow validation
- ORM/Security: Access rights per group, multi-company rules, cashier denial, manager permissions, admin config
- Integration: Create POS order -> pending -> run analysis -> create case/reasons -> activity -> manager reviews -> reports include outcome
- Regression: Ordinary sale, discounted sale, refund, offline sync, session closing, module disabled, upgrade with existing orders
- Perf: 100 orders batch <60s dev env, 10k historical, no query explosion, small event payload

## 15. Definition of Done per Feature
- Follows Odoo 19 conventions, no core modification
- Security + record rules defined
- Views usable, translatable strings
- Automated positive/negative tests, existing tests pass
- Installs/upgrades successfully
- No unrelated code changed
- Edge cases documented
- Acceptance criteria demonstrated
- Phase checklist updated

## 16. Required Prompt Pattern for Each Phase
User must prompt like:
"Read PRD.md completely. Implement only Phase X: <phase name>, specifically: - <feature one> - <feature two> First inspect repo and Odoo 19 source. Then provide brief plan. Do not implement later phases or add unapproved dependencies. Add automated tests for acceptance criteria. Run relevant tests and report exact results."

## 17. Open Decisions to Resolve in Phase 0
1. Community vs Enterprise 2. Custom addon path/namespace 3. Cashier identity: pos.order.user_id vs hr 4. Test/CI commands 5. Event sync: extend order payload vs separate method 6. Responsible managers config per POS/company 7. Deploy env + sklearn permission 8. Currency strategy 9. Retention period 10. Cancelled unpaid orders sync for cancellation monitoring

## 18. Final Release Acceptance
1. Enable monitoring per POS 2. Configure one rule per category 3. Complete normal/abnormal POS transactions 4. Capture override/deletion events 5. Analyze backend 6. Generate correct scores/levels 7. Create explainable cases without duplicates 8. Notify manager for high-risk 9. Review/classify case 10. View outcome in reports 11. Compare with baseline 12. Ordinary POS works when disabled/unavailable
