# Product Requirements Document

## Intelligent POS Transaction Monitoring for Cashier Error Detection and Fraud Risk Analysis

| Document field | Value |
|---|---|
| Product | Odoo 19 POS Cashier Risk Monitor |
| Technical addon name | `pos_cashier_risk_monitor` |
| Platform | Odoo 19 |
| Document type | Product and implementation requirements |
| Intended audience | Claude or another implementation agent, project developer, reviewer and examiner |
| Delivery strategy | Incremental, feature-by-feature |
| Status | Approved for implementation planning |

---

## 1. Purpose of this document

This PRD defines a complete implementation plan for an Odoo 19 custom addon that monitors Point of Sale transactions for:

- Accidental cashier mistakes
- Unusual or excessive discounts
- Drastic manual price changes
- Excessive line deletion, void and cancellation activity
- Abnormal or unlinked refunds
- Repeated policy violations
- Behavioural anomalies compared with historical activity
- Potential fraud-risk indicators requiring human investigation

The document is written so that Claude can implement the project one feature at a time without inventing missing requirements, mixing phases or prematurely introducing machine learning.

The system must identify **risk and abnormal activity**, not declare that an employee committed fraud. The final decision always belongs to an authorized reviewer.

---

## 2. Product vision

Retail ERP systems preserve transactions, stock movements and payments, but managers cannot manually inspect every cashier operation. A transaction can be technically valid while still being accidental, unusual, financially harmful or suspicious.

The product will continuously analyze completed POS transactions, assign explainable risk scores, create review cases for significant activity and allow managers to record the outcome.

### 2.1 Product statement

> A configurable Odoo POS monitoring addon that detects cashier errors and suspicious transaction patterns, compares them with expected behaviour, estimates financial exposure and creates explainable cases for authorized stakeholders.

### 2.2 Primary value

- Reduce the time spent manually auditing POS transactions.
- Identify revenue leakage caused by mistakes or policy violations.
- Prioritize the transactions that require managerial attention.
- Explain why each transaction was considered unusual.
- Preserve reviewer feedback for future analysis and model evaluation.
- Provide a reusable commercial feature for retail ERP deployments.

---

## 3. Terminology and language rules

These definitions must be used consistently in code, user interfaces and documentation.

| Term | Meaning |
|---|---|
| Event | A cashier action captured during a POS order, such as deleting a line or manually changing a price. |
| Signal | A measurable condition contributing to risk, such as a discount above 25%. |
| Rule | A configurable deterministic condition evaluated against an order, line or event. |
| Baseline | Historical values describing expected behaviour for a cashier, POS or company. |
| Anomaly | An activity significantly different from its applicable baseline. |
| Risk case | A manager-facing record created when an analyzed transaction exceeds the configured case threshold. |
| Fraud risk | Suspicious evidence requiring investigation; it is not proof of fraud. |
| Financial exposure | Estimated monetary value potentially affected by the abnormal action. |
| Reviewer feedback | The manager's classification after investigating a risk case. |

### 3.1 Prohibited wording

The system must not automatically display statements such as:

- "The cashier committed fraud."
- "This employee is fraudulent."
- "Fraud confirmed" without a manager explicitly recording an investigation outcome.

Preferred wording:

- "Potential fraud-risk activity"
- "Suspicious transaction requiring review"
- "Unusual cashier activity"
- "Possible cashier error"

---

## 4. Goals and non-goals

### 4.1 Goals

1. Create an installable Odoo 19 addon using standard Odoo conventions.
2. Monitor four initial categories: discounts, price overrides, deleted/voided activity and refunds.
3. Capture temporary POS UI actions that are not reliably available after order synchronization.
4. Detect known exceptions using configurable business rules.
5. Compare transactions with historical cashier or store behaviour.
6. Produce a risk score between 0 and 100.
7. Generate human-readable reasons and recommended actions.
8. Create risk cases without blocking the POS payment workflow.
9. Notify authorized managers about high-priority cases.
10. Record investigation outcomes and false positives.
11. Provide list, kanban, graph and pivot analysis.
12. Include automated tests and demonstration data.

### 4.2 Non-goals for the first release

- Facial recognition or video surveillance
- Automatic employee punishment or account blocking
- Automatic reversal of POS transactions
- Real-time blocking of discounts or refunds
- Credit-card fraud detection
- Customer identity verification
- Deep-learning or neural-network models
- External cloud AI services
- Cross-company sharing of sensitive investigation data
- Replacing Odoo's standard POS authorization controls
- Full stock-movement anomaly detection

These may be evaluated only after the core project is complete.

---

## 5. Users and permissions

### 5.1 Personas

#### Cashier

- Operates Odoo POS normally.
- Must not experience meaningful payment delay.
- Does not access risk cases concerning themselves or other cashiers.
- May be asked to provide an optional reason for a manual override if enabled.

#### Risk monitoring user

- Can view cases explicitly assigned to them.
- Can add investigation notes.
- Cannot configure detection rules.

#### Risk manager

- Can view company risk cases.
- Can start, classify and close investigations.
- Can create activities for other reviewers.
- Can view dashboards and reports.

#### Risk administrator

- Has all manager permissions.
- Configures rules, thresholds, scheduled processing and notification settings.
- Can retrain or recalculate behavioural models.

### 5.2 Security groups

Create the following XML groups:

```text
group_pos_risk_user
group_pos_risk_manager
group_pos_risk_admin
```

Group inheritance:

```text
Risk Administrator → Risk Manager → Risk Monitoring User
```

### 5.3 Security requirements

- Every business record must contain `company_id` where appropriate.
- Multi-company record rules must use the current user's allowed companies.
- Cashiers must not receive read access to `pos.risk.case` or `pos.risk.case.reason` by default.
- Only risk administrators may create, update or delete rule definitions.
- Risk cases must not normally be deleted; administrators may archive them.
- Reviewer actions must be recorded in chatter.
- User-facing methods must not use unrestricted `sudo()`.

---

## 6. Initial functional scope

### 6.1 Discount monitoring

The system must detect:

- Discount percentage above a configured absolute threshold
- Discount much higher than the cashier's historical average
- Multiple highly discounted orders in a short period
- Discount that causes a negative margin
- Repeated use of the maximum permitted discount
- High discount applied repeatedly for the same customer

### 6.2 Price-override monitoring

The system must detect:

- Manual price decrease above a configured percentage
- Manual price increase above a configured percentage
- Final unit price below cost
- Repeated manual overrides during one session
- Multiple changes to the same line
- Price override followed by line deletion or refund

### 6.3 Deleted, voided and cancelled activity

The system must detect:

- Deleted-line count above a configured threshold
- Deleted high-value item
- Repeated order cancellation
- Deletion after a manual price change or discount
- Unusual deletion frequency compared with cashier history

Only actions that can be captured reliably in Odoo 19 are in release scope. A standard completed order may not preserve every action taken before validation, so a custom POS event log is required.

### 6.4 Refund monitoring

The system must detect:

- High-value refund
- Refund line without a valid original POS order-line relationship
- Refund amount unusually high for the cashier or POS
- Multiple refunds in a configurable rolling time window
- Refund associated with repeated activity for the same customer
- Different refund behaviour compared with historical activity

---

## 7. High-level architecture

```text
Odoo POS frontend
    ↓ captures temporary cashier events
POS order and event synchronization
    ↓ marks order as pending analysis
Backend feature extraction
    ├── configurable rule engine
    ├── historical baseline engine
    └── anomaly model (later phase)
    ↓
Combined risk scoring
    ↓
Explainable risk case
    ↓
Manager notification, review and feedback
```

### 7.1 Architectural principles

1. Do not block or materially slow POS payment validation.
2. Use standard Odoo models wherever the information already exists.
3. Store only additional facts that cannot be reconstructed later.
4. Make analysis idempotent and retryable.
5. Keep detection logic outside ORM model methods where possible.
6. Separate rule evaluation, feature extraction, scoring and explanation generation.
7. Deliver a fully usable rule-based release before adding machine learning.
8. Do not modify Odoo core source files.

---

## 8. Technical addon definition

### 8.1 Manifest

Initial dependencies:

```python
"depends": [
    "point_of_sale",
    "mail",
]
```

Do not add `stock`, `hr`, `pos_hr`, `queue_job` or Scikit-learn-related requirements until the feature requiring them is approved.

The addon must be installable on a clean Odoo 19 database with Point of Sale installed.

### 8.2 Suggested directory structure

```text
pos_cashier_risk_monitor/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── pos_order.py
│   ├── pos_order_line.py
│   ├── risk_rule.py
│   ├── risk_event.py
│   ├── risk_case.py
│   ├── risk_case_reason.py
│   ├── cashier_baseline.py
│   └── res_config_settings.py
├── services/
│   ├── __init__.py
│   ├── feature_extractor.py
│   ├── rule_engine.py
│   ├── baseline_engine.py
│   ├── anomaly_engine.py
│   ├── risk_calculator.py
│   └── explanation_engine.py
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
├── data/
│   ├── sequence_data.xml
│   ├── risk_rule_data.xml
│   ├── cron_data.xml
│   └── mail_activity_data.xml
├── views/
│   ├── risk_rule_views.xml
│   ├── risk_event_views.xml
│   ├── risk_case_views.xml
│   ├── cashier_baseline_views.xml
│   ├── pos_order_views.xml
│   ├── res_config_settings_views.xml
│   └── menu_views.xml
├── static/src/
│   ├── js/pos_event_tracker.js
│   ├── xml/pos_event_templates.xml
│   └── scss/risk_monitor.scss
├── tests/
│   ├── __init__.py
│   ├── common.py
│   ├── test_security.py
│   ├── test_rule_engine.py
│   ├── test_analysis_job.py
│   └── test_case_workflow.py
├── demo/
│   └── demo_data.xml
└── README.md
```

Service modules must contain ordinary Python logic and should avoid tightly coupling algorithms to views or controllers.

---

## 9. Data model requirements

Field names below are normative unless an Odoo 19 conflict requires a documented change.

### 9.1 Extend `pos.order`

| Field | Type | Requirements |
|---|---|---|
| `risk_analysis_state` | Selection | `not_required`, `pending`, `processing`, `completed`, `failed`; indexed; default determined after order completion |
| `risk_score` | Float | Stored final score from 0 to 100 |
| `risk_level` | Selection | `none`, `low`, `medium`, `high`, `critical` |
| `risk_case_count` | Integer | Computed count of associated cases |
| `risk_analyzed_at` | Datetime | Last successful analysis timestamp |
| `risk_analysis_error` | Text | Technical failure summary visible only to administrators |
| `risk_case_ids` | One2many | Associated `pos.risk.case` records |

Add a smart button on the backend POS order form when at least one risk case exists.

### 9.2 Extend `pos.order.line`

| Field | Type | Requirements |
|---|---|---|
| `risk_original_unit_price` | Float | Applicable unit price before manual cashier intervention |
| `risk_is_manual_price_override` | Boolean | True only for a cashier/manual override, not a pricelist-calculated price |
| `risk_price_override_difference` | Monetary or Float | Final price minus original applicable price |
| `risk_price_override_percentage` | Float | Absolute percentage difference; safely handles zero original price |
| `risk_price_override_reason` | Char | Optional cashier/manager reason |
| `risk_manual_price_change_count` | Integer | Number of captured manual changes for this line |

Do not compare only against `product.lst_price`. The original reference must be the effective POS/pricelist price immediately before manual intervention.

### 9.3 Model `pos.risk.event`

Purpose: preserve temporary actions performed in the POS frontend.

Required fields:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Human-readable event label |
| `event_uuid` | Char | Required, unique, generated in frontend or backend |
| `order_uuid` | Char | POS order UUID used before database relation exists |
| `order_id` | Many2one | `pos.order`, set after synchronization |
| `order_line_uuid` | Char | Client-side line identifier if available |
| `order_line_id` | Many2one | `pos.order.line`, optional |
| `cashier_id` | Many2one | `res.users` |
| `session_id` | Many2one | `pos.session` |
| `config_id` | Many2one | `pos.config` |
| `company_id` | Many2one | Required and indexed |
| `product_id` | Many2one | Optional `product.product` |
| `event_type` | Selection | Defined below |
| `old_numeric_value` | Float | Previous numeric value |
| `new_numeric_value` | Float | New numeric value |
| `quantity` | Float | Related quantity if relevant |
| `currency_id` | Many2one | Company or POS currency |
| `event_at` | Datetime | Client event time normalized to UTC |
| `server_received_at` | Datetime | Backend reception time |
| `reason` | Char | Optional explanation |
| `metadata_json` | Json | Only non-sensitive additional context |
| `processed` | Boolean | Analysis-processing flag |

Supported initial event types:

```text
discount_applied
price_overridden
line_deleted
quantity_changed
refund_started
order_cancelled
payment_cancelled
```

Constraints:

- SQL uniqueness constraint on `event_uuid`.
- Reject malformed events without crashing POS order synchronization.
- Do not store arbitrary frontend objects in `metadata_json`.
- Do not trust frontend-supplied company, cashier or monetary values without backend validation.

### 9.4 Model `pos.risk.rule`

Required fields:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required |
| `code` | Char | Required, immutable after use, unique per company or global scope |
| `active` | Boolean | Supports archive behaviour |
| `company_id` | Many2one | Empty means shared/default rule only if explicitly supported |
| `config_ids` | Many2many | Optional POS limitation |
| `category` | Selection | `discount`, `price_override`, `deletion`, `cancellation`, `refund`, `timing`, `combined` |
| `scope` | Selection | `order`, `line`, `event`, `cashier_window` |
| `operator` | Selection | Safe supported operators only; never execute arbitrary Python expressions |
| `threshold_value` | Float | Primary comparison value |
| `secondary_threshold_value` | Float | Optional range/window value |
| `window_minutes` | Integer | Rolling window for frequency rules |
| `minimum_amount` | Monetary | Ignore financially insignificant activity |
| `severity_score` | Float | 0–100 |
| `risk_weight` | Float | Non-negative weighting |
| `case_classification` | Selection | Suggested classification when triggered |
| `description` | Text | Business explanation |
| `recommended_action` | Text | Displayed on generated case |

Do not allow administrators to provide executable Python code or unsafe domains as rule logic. Implement an explicit registry of supported rule evaluators keyed by `code` or `rule_type`.

### 9.5 Model `pos.cashier.baseline`

Required fields:

| Field | Type | Notes |
|---|---|---|
| `cashier_id` | Many2one | Optional for POS/company fallback baselines |
| `config_id` | Many2one | Optional POS scope |
| `company_id` | Many2one | Required |
| `baseline_level` | Selection | `cashier`, `pos`, `company` |
| `period_start` | Date | Historical period start |
| `period_end` | Date | Historical period end |
| `sample_count` | Integer | Number of valid analyzed orders |
| `avg_discount_pct` | Float | Mean discount percentage |
| `std_discount_pct` | Float | Standard deviation |
| `p95_discount_pct` | Float | 95th percentile |
| `avg_price_override_pct` | Float | Mean manual price deviation |
| `std_price_override_pct` | Float | Standard deviation |
| `avg_deleted_lines` | Float | Mean per order |
| `p95_deleted_lines` | Float | 95th percentile |
| `avg_refund_amount` | Monetary | Mean refund amount |
| `p95_refund_amount` | Monetary | 95th percentile |
| `refund_frequency` | Float | Refund orders divided by analyzed orders |
| `calculated_at` | Datetime | Calculation timestamp |

Uniqueness must prevent two baselines for the same subject and historical period.

Fallback order:

```text
Cashier baseline with sufficient sample → POS baseline → Company baseline
```

Default minimum cashier sample size: `30` completed orders.

### 9.6 Model `pos.risk.case`

Required fields:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence-generated case number |
| `active` | Boolean | Archive instead of delete |
| `fingerprint` | Char | Required unique idempotency key |
| `company_id` | Many2one | Required, indexed |
| `order_id` | Many2one | Required `pos.order` |
| `order_line_id` | Many2one | Optional |
| `event_ids` | Many2many | Supporting captured events |
| `cashier_id` | Many2one | `res.users`, required when known |
| `session_id` | Many2one | POS session |
| `config_id` | Many2one | POS configuration |
| `category` | Selection | Same primary categories as rules |
| `classification` | Selection | Defined below |
| `rule_score` | Float | 0–100 |
| `anomaly_score` | Float | 0–100 |
| `impact_score` | Float | 0–100 |
| `risk_score` | Float | Final 0–100 score |
| `risk_level` | Selection | `low`, `medium`, `high`, `critical` |
| `currency_id` | Many2one | Related monetary currency |
| `financial_exposure` | Monetary | Estimated affected value |
| `explanation` | Text/Html | Human-readable; sanitize if HTML |
| `recommended_action` | Text | Review guidance |
| `state` | Selection | Workflow defined below |
| `assigned_user_id` | Many2one | Reviewer |
| `reviewed_by` | Many2one | User who recorded outcome |
| `reviewed_at` | Datetime | Outcome timestamp |
| `review_outcome` | Selection | Defined below |
| `review_notes` | Text | Required for selected outcomes |
| `detected_at` | Datetime | Case creation time |
| `model_version` | Char | Optional anomaly model version |

The model must inherit `mail.thread` and `mail.activity.mixin`.

Case classifications:

```text
possible_error
policy_violation
behavioural_anomaly
fraud_risk
requires_review
```

Case workflow:

```text
new → under_review → resolved → closed
```

Permitted shortcuts:

- `new → closed` only when marked as duplicate with a linked original case.
- Reopening a closed case must require risk manager permission and create a chatter message.

Review outcomes:

```text
cashier_mistake
policy_violation
training_required
suspicious_activity
configuration_issue
valid_business_operation
false_positive
duplicate
```

### 9.7 Model `pos.risk.case.reason`

Each case may contain multiple reason lines.

Required fields:

- `case_id`
- `rule_id`, optional for model-derived reasons
- `reason_code`
- `description`
- `observed_value`
- `expected_value`
- `deviation_value`
- `contribution_score`
- `financial_exposure`
- `sequence`

Reasons must be understandable without looking at server logs.

---

## 10. Configuration requirements

Add settings through `res.config.settings`, backed by `pos.config`, company settings or `ir.config_parameter` as appropriate.

Initial settings:

| Setting | Default |
|---|---:|
| Enable POS risk monitoring | False per POS configuration |
| Analyze completed orders automatically | True |
| Case-creation score threshold | 40 |
| High-risk threshold | 70 |
| Critical-risk threshold | 85 |
| Minimum cashier baseline sample | 30 |
| Baseline lookback days | 90 |
| Create activity for high-risk case | True |
| Notify for critical cases | True |
| Require manual price-change reason | False |
| Rule-score weight | 0.45 |
| Anomaly-score weight | 0.35 |
| Impact-score weight | 0.20 |

Validate that score weights total `1.0`, allowing a small floating-point tolerance.

---

## 11. Initial rule catalogue

Install inactive or conservatively configured default rules. Administrators must be able to adjust them.

| Code | Condition | Default severity |
|---|---|---:|
| `HIGH_DISCOUNT` | Maximum line discount is at least 25% | 60 |
| `NEGATIVE_MARGIN` | Final selling value is below available cost reference | 85 |
| `DRASTIC_PRICE_DECREASE` | Manual price decrease is at least 30% | 75 |
| `DRASTIC_PRICE_INCREASE` | Manual price increase is at least 30% | 55 |
| `EXCESSIVE_LINE_DELETION` | More than 3 captured deleted lines in one order | 65 |
| `HIGH_VALUE_LINE_DELETION` | Deleted-line value exceeds configured amount | 75 |
| `UNLINKED_REFUND` | Refund line lacks a valid original line link | 90 |
| `HIGH_VALUE_REFUND` | Refund total exceeds configured amount | 70 |
| `REPEATED_REFUNDS` | At least 3 refunds within 60 minutes | 80 |
| `COMBINED_OVERRIDE_DELETE` | Manual override and subsequent deletion on related activity | 85 |

Currency-specific default amount thresholds must not be hard-coded globally. Configure monetary thresholds per company or use demonstration values only.

---

## 12. Feature extraction

Create a service that converts an order and its events into a stable dictionary. The rule and anomaly engines must consume this dictionary instead of repeatedly querying fields independently.

Minimum features:

```text
order_id
company_id
config_id
session_id
cashier_id
order_datetime
order_total
absolute_order_total
line_count
discounted_line_count
max_discount_pct
average_discount_pct
discount_amount
manual_override_count
max_price_deviation_pct
price_override_exposure
deleted_line_count
deleted_line_value
is_refund
refund_amount
refund_line_count
unlinked_refund_line_count
customer_id
hour_of_day
cashier_recent_refund_count
cashier_recent_high_discount_count
```

Feature extraction requirements:

- Use company/POS currency consistently.
- Safely handle zero prices, missing customers and missing costs.
- Do not treat a standard pricelist price as a manual override.
- Treat negative quantities carefully and distinguish refunds from ordinary sales.
- Return deterministic output for the same unchanged data.
- Avoid one query per order line.

---

## 13. Risk calculation

### 13.1 Component scores

Every component score must be normalized to `0–100`.

- `rule_score`: aggregated score from triggered deterministic rules.
- `anomaly_score`: difference from baseline or ML anomaly result.
- `impact_score`: normalized estimated financial exposure.

### 13.2 Initial combined formula

```text
final_score =
    (rule_score × rule_weight) +
    (anomaly_score × anomaly_weight) +
    (impact_score × impact_weight)
```

Default weights:

```text
rule_weight = 0.45
anomaly_weight = 0.35
impact_weight = 0.20
```

Before the anomaly engine is enabled, redistribute or normalize available components rather than automatically lowering every result. The exact fallback formula must be covered by tests and documented.

### 13.3 Risk levels

| Score | Risk level | Default behaviour |
|---:|---|---|
| 0–39.99 | Low | Save analysis; no case unless configured |
| 40–69.99 | Medium | Create a review case |
| 70–84.99 | High | Create case and manager activity |
| 85–100 | Critical | Priority case and immediate configured notification |

Clamp all final scores to `0–100`.

### 13.4 Financial exposure

Examples:

```text
Discount exposure = max(reference price − final price, 0) × quantity
Price-decrease exposure = max(original price − final price, 0) × quantity
Refund exposure = absolute refund value
Deleted-line exposure = captured deleted price × captured deleted quantity
```

Do not claim that exposure equals confirmed loss.

---

## 14. Explainability requirements

Every created case must answer:

1. What happened?
2. Why is it unusual or risky?
3. What value was observed?
4. What value or threshold was expected?
5. What is the estimated financial exposure?
6. What should the reviewer do next?

Example:

> A 32% discount was applied, exceeding the configured 20% threshold. The cashier's 90-day average discount is 4.6%. The final price is below the available cost reference. Estimated exposure: 1,850. Review the transaction and verify authorization.

The first release must generate explanations from rule reasons and statistical deviations. SHAP is not required for the first ML release.

---

## 15. Background processing and idempotency

### 15.1 Processing model

Do not run full analysis synchronously in the payment-validation path.

When an eligible order is completed:

1. Set `risk_analysis_state = pending`.
2. A scheduled action selects a limited batch of pending or safely retryable orders.
3. Mark selected orders `processing`.
4. Extract features and evaluate rules.
5. Calculate scores and create/update required cases.
6. Mark orders `completed` and set `risk_analyzed_at`.
7. On recoverable failure, mark `failed`, store a safe error summary and allow administrative retry.

### 15.2 Scheduled jobs

| Job | Initial frequency | Purpose |
|---|---|---|
| Analyze pending POS orders | Every 5 minutes | Main risk processing |
| Recalculate behavioural baselines | Nightly | Update cashier/POS/company statistics |
| Retrain anomaly models | Weekly, later phase | Refresh Isolation Forest models |

### 15.3 Idempotency

Case fingerprint must deterministically represent:

```text
company + order + optional line/event + category + applicable rule/model version
```

Re-running analysis must not create duplicate cases or activities.

Batch size must be configurable. Initial default: `100` orders.

---

## 16. Manager user interface

### 16.1 Menu structure

```text
Point of Sale
└── Risk Monitoring
    ├── Dashboard
    ├── Risk Cases
    ├── Cashier Analysis
    ├── Behavioural Baselines
    ├── Rules
    └── Configuration
```

### 16.2 Risk-case list

Columns:

- Case number
- Detection time
- Cashier
- POS
- POS order
- Category
- Classification
- Financial exposure
- Risk score
- Risk level
- State
- Assigned reviewer

Provide search filters for:

- My assigned cases
- New and under review
- High and critical
- Cashier
- POS configuration
- Category
- Review outcome
- Detection date

### 16.3 Risk-case form

Display:

- Risk score and level
- Cashier, order, session and POS
- Explanation and recommended action
- Financial exposure
- Triggered reason lines
- Supporting events
- Review controls
- Chatter and activities

Buttons must enforce valid state transitions.

### 16.4 Reports

Use standard Odoo graph and pivot views before creating a custom OWL dashboard.

Required measures and dimensions:

- Case count
- Total estimated exposure
- Average risk score
- Cases by cashier
- Cases by POS
- Cases by category
- Cases by risk level
- Cases by review outcome
- False-positive rate
- Trend by day, week and month

---

## 17. Notifications

For high-risk cases:

- Create one `mail.activity` for the configured risk manager or responsible group.
- Do not create duplicate activities during re-analysis.

For critical cases:

- Create a high-priority activity.
- Optionally send an email or Odoo inbox notification if configured.

Notifications must include:

- Case reference
- POS order
- Cashier
- Risk level and score
- Short explanation
- Estimated exposure
- Link to the case

Do not send investigation details to unauthorized recipients.

---

## 18. Behavioural baseline engine

This feature begins only after deterministic rule detection is accepted.

### 18.1 Historical population

Use completed POS transactions from a configurable lookback period, initially 90 days.

Exclude where appropriate:

- Cancelled or incomplete orders
- Corrupt demonstration records
- Orders missing essential company/POS information
- The current order being scored

### 18.2 Statistics

Calculate mean, standard deviation and relevant percentiles for discount, overrides, deletions and refunds.

Example standardized deviation:

```text
z_score = (observed_value − mean) / standard_deviation
```

Handle zero standard deviation explicitly.

### 18.3 Context resolution

1. Use cashier baseline when sample size is sufficient.
2. Otherwise use POS-configuration baseline.
3. Otherwise use company baseline.
4. If no baseline is available, use only deterministic rules and record that anomaly scoring was unavailable.

The selected baseline and sample size must be visible in reason details.

---

## 19. Machine-learning enhancement

Machine learning is a later feature and must not be required for installing the base addon.

### 19.1 Initial algorithm

Use Isolation Forest for unsupervised anomaly detection.

### 19.2 Initial features

```text
maximum discount percentage
discount amount relative to order total
maximum manual price deviation
manual override count
deleted-line count
deleted-line value relative to order total
refund amount
refund-line count
unlinked-refund count
order total
line count
hour-of-day encoding
cashier recent refund frequency
cashier recent high-discount frequency
```

### 19.3 Training strategy

- Start with one model per company or POS configuration, not one model per cashier.
- Include cashier historical statistics as contextual features.
- Train sales and refunds separately if testing demonstrates materially different distributions.
- Use 60–90 days of valid historical data.
- Store model metadata: version, training period, features, sample count and parameters.
- Do not silently score with a model trained for another company.

### 19.4 Dependency isolation

Before adding Scikit-learn:

1. Confirm supported Python version and deployment environment.
2. Add the dependency explicitly to project installation requirements.
3. Make the ML engine disable gracefully when the dependency or a trained model is unavailable.
4. Keep deterministic analysis functional.

### 19.5 Interpretation

The anomaly score alone must never create an accusation. A case must state which feature deviations contributed most, using understandable statistical comparisons.

---

## 20. Functional requirement catalogue

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Install addon on clean Odoo 19 POS database | Must |
| FR-002 | Configure monitoring per POS | Must |
| FR-003 | Capture manual price override metadata | Must |
| FR-004 | Capture deleted-line events | Must |
| FR-005 | Evaluate configurable discount rules | Must |
| FR-006 | Evaluate price-override rules | Must |
| FR-007 | Evaluate deletion/cancellation rules | Must |
| FR-008 | Evaluate refund rules | Must |
| FR-009 | Analyze orders outside payment path | Must |
| FR-010 | Create idempotent risk cases | Must |
| FR-011 | Produce multiple explainable reasons | Must |
| FR-012 | Allow manager review workflow | Must |
| FR-013 | Record review outcome and notes | Must |
| FR-014 | Enforce multi-company security | Must |
| FR-015 | Notify manager for high/critical case | Should |
| FR-016 | Calculate cashier/POS/company baselines | Should |
| FR-017 | Generate statistical anomaly scores | Should |
| FR-018 | Provide graph and pivot analysis | Should |
| FR-019 | Score transactions with Isolation Forest | Could, after core completion |
| FR-020 | Produce custom OWL dashboard | Could, after standard reporting |

---

## 21. Non-functional requirements

### 21.1 Performance

- The event-capture patch must not noticeably delay normal POS interaction.
- Order validation must not wait for complete risk analysis.
- Initial target: analyze 100 ordinary orders in under 60 seconds on the development environment.
- Avoid N+1 queries.
- Add indexes to frequently searched fields such as analysis state, company, detection date, risk level, case state and fingerprint.

### 21.2 Reliability

- A malformed event must not prevent the sale from being synchronized.
- Failed analysis must be retryable.
- Re-analysis must not duplicate cases or notifications.
- Processing must be safe if a scheduled action runs concurrently.

### 21.3 Maintainability

- Follow Odoo 19 coding conventions.
- No Odoo core modifications.
- Keep algorithms in service classes/modules.
- Every configurable rule evaluator must have automated tests.
- Add docstrings where business reasoning is not obvious.
- Avoid magic numbers; use settings or named constants.

### 21.4 Privacy and auditability

- Store only data necessary for risk analysis.
- Restrict cases and event logs to authorized groups.
- Preserve manager outcome changes in chatter.
- Provide archival/retention configuration before production use.

---

## 22. Incremental implementation plan

Claude must implement one phase at a time. Each phase must be reviewed and accepted before the next begins.

### Phase 0 — Repository and environment verification

#### Objective

Confirm the actual Odoo 19 addon repository, conventions and development commands.

#### Tasks

1. Inspect the repository structure and existing `AGENTS.md`, contributor instructions and addon conventions.
2. Confirm Odoo 19 source and custom addon paths.
3. Confirm Community or Enterprise environment.
4. Identify the standard Odoo 19 POS fields and frontend extension points from the installed source.
5. Document install, upgrade and test commands.
6. Do not write production code in this phase unless explicitly requested.

#### Exit criteria

- Repository instructions are understood.
- Exact source fields and extension methods are verified.
- No assumptions about an older Odoo version remain.

---

### Phase 1 — Installable addon scaffold

#### Objective

Create the smallest valid addon.

#### Deliverables

- Manifest and initialization files
- Base menu category
- Three security groups
- Empty settings section or monitoring enable flag
- Basic README
- Installation smoke test

#### Acceptance criteria

- Module appears in Apps when appropriate filters are removed.
- Module installs and upgrades without warnings caused by custom code.
- Uninstall succeeds on a disposable database.
- No frontend assets are added yet.

#### Tests

- Install/upgrade smoke test
- Access-group XML loads correctly

#### Stop gate

Do not implement risk rules, POS patches or ML before this phase is accepted.

---

### Phase 2 — Configuration and rule master

#### Objective

Allow administrators to configure monitoring and deterministic rules.

#### Deliverables

- `pos.risk.rule`
- Monitoring settings
- Rule list/form/search views
- Initial rule data
- Admin-only write access
- Validation for thresholds, weights and windows

#### Acceptance criteria

- Administrator can activate/deactivate and configure a rule.
- Manager can read but not alter rule configuration unless explicitly granted.
- Cashier cannot access rule menus.
- Arbitrary Python expressions cannot be stored or executed.
- Invalid weights or negative thresholds are rejected with clear messages.

#### Tests

- Model constraints
- Security access
- Multi-company visibility
- Rule archive behaviour

---

### Phase 3 — Risk-case workflow

#### Objective

Build the manager review workflow before automated detection creates cases.

#### Deliverables

- `pos.risk.case`
- `pos.risk.case.reason`
- Case sequence
- List, form, kanban and search views
- State-transition methods
- Chatter and activities
- Manual test-case creation available only to administrators or tests

#### Acceptance criteria

- Case receives a unique sequence.
- Manager can move a case through valid states.
- Invalid state transition raises a user-friendly error.
- Outcome and reviewer metadata are captured.
- Required notes are enforced where configured.
- Cashier cannot view cases.
- Reopening a closed case is audited.

#### Tests

- Workflow transitions
- Review outcome validation
- Security and record rules
- Fingerprint uniqueness

---

### Phase 4 — Backend POS model extensions

#### Objective

Prepare standard POS orders and lines for risk analysis.

#### Deliverables

- `pos.order` analysis fields and smart button
- `pos.order.line` price-override metadata fields
- Pending-analysis marking for eligible completed orders
- Manual "Analyze" and "Retry Analysis" administrator actions

#### Acceptance criteria

- Monitoring-disabled POS orders are marked `not_required`.
- Monitoring-enabled completed orders become `pending`.
- Reopening or updating unrelated fields does not create duplicate cases.
- Existing POS flows remain functional.
- Smart button respects access rights.

#### Tests

- Enabled versus disabled POS configuration
- Order-state transitions
- Multi-company behaviour
- Existing order without custom values

---

### Phase 5 — POS frontend event capture

#### Objective

Capture temporary cashier actions safely using Odoo 19 OWL extension mechanisms.

#### Deliverables

- `pos.risk.event`
- Frontend patch for manual price changes and line deletion
- Event UUID generation
- Event synchronization/reconciliation with backend order
- Optional manual override reason prompt when enabled

#### Acceptance criteria

- Manual price override captures original and final applicable prices.
- Pricelist-driven price changes are not incorrectly marked manual.
- Deleted-line event preserves product, quantity and price context.
- Repeated synchronization does not duplicate events.
- Offline-created orders synchronize events after reconnection.
- Invalid event payload does not cause order loss.
- Monitoring-disabled POS does not collect unnecessary custom events.

#### Tests

- JavaScript/OWL tests where supported
- Backend payload validation tests
- Duplicate UUID test
- Offline/retry synchronization scenario

#### Stop gate

Do not assume frontend fields or patch targets from Odoo 16. Verify them against Odoo 19 source.

---

### Phase 6 — Feature extraction service

#### Objective

Create one deterministic data representation used by every detector.

#### Deliverables

- `feature_extractor.py`
- Feature schema documentation
- Query-efficient batch extraction
- Unit tests for sales, discounts, overrides, deletions and refunds

#### Acceptance criteria

- Same order data produces the same feature values.
- Zero prices and missing optional data do not crash extraction.
- Refunds are distinguished from sales.
- Standard pricelist changes are not classified as manual overrides.
- No N+1 query behaviour in tested batches.

---

### Phase 7 — Deterministic rule engine

#### Objective

Deliver the first complete automated detection capability.

#### Deliverables

- Safe evaluator registry
- Initial rule implementations
- Rule-result data structure
- Financial-exposure calculation
- Explanation reason generation

#### Rule-result contract

```python
{
    "triggered": True,
    "rule_code": "HIGH_DISCOUNT",
    "category": "discount",
    "score": 60.0,
    "financial_exposure": 450.0,
    "observed_value": 32.0,
    "expected_value": 20.0,
    "reason": "Discount is 32%, exceeding the configured 20% threshold.",
    "recommended_action": "Verify manager authorization.",
}
```

#### Acceptance criteria

- Each initial rule has positive and negative tests.
- Disabled rules never trigger.
- Company/POS-specific rules apply only in scope.
- Missing cost does not falsely generate negative-margin claims.
- Rule results contain understandable observed and expected values.

---

### Phase 8 — Analysis job, scoring and case creation

#### Objective

Connect order processing, feature extraction, rules, scoring and cases.

#### Deliverables

- Five-minute scheduled action
- Batch processing
- Score calculation
- Case threshold handling
- Idempotent case creation/update
- Failure and retry handling

#### Acceptance criteria

- Pending orders are processed without blocking POS validation.
- Low-risk order completes analysis without unnecessary case creation.
- Medium/high/critical transaction creates the correct case level.
- Re-running the job creates no duplicate case or reasons.
- One failed order does not roll back successful analysis of the entire batch when safe processing boundaries are used.
- Administrator can retry a failed order.

#### Tests

- End-to-end rule-based case creation
- Scheduled job re-run
- Duplicate fingerprint
- Batch containing one malformed order
- Concurrent processing strategy

#### Milestone

At this phase, the project is a complete running rule-based product and can be demonstrated.

---

### Phase 9 — Manager notifications

#### Objective

Ensure important cases reach an authorized stakeholder.

#### Deliverables

- Responsible manager configuration
- High-risk activity creation
- Critical notification option
- Idempotent notification logic

#### Acceptance criteria

- High and critical cases notify the correct authorized user.
- Medium cases do not notify unless configured.
- Re-analysis does not duplicate activities.
- Notification links open the permitted case.

---

### Phase 10 — Behavioural baselines

#### Objective

Compare current transactions with historical context.

#### Deliverables

- `pos.cashier.baseline`
- Nightly calculation job
- Cashier → POS → company fallback
- Statistical anomaly reasons
- Manual recalculation action

#### Acceptance criteria

- Cashier baseline is used only when minimum sample size is met.
- Fallback baseline is clearly recorded.
- Current order is not included in its own baseline.
- Zero standard deviation is handled safely.
- Statistical reasons display sample size and expected values.
- Recalculation is idempotent.

---

### Phase 11 — Hybrid score integration

#### Objective

Combine deterministic rule evidence with statistical abnormality.

#### Deliverables

- Anomaly component score
- Configurable weighted formula
- Updated explanation output
- Comparison report: rule-only versus hybrid

#### Acceptance criteria

- Score remains within 0–100.
- Weights are validated.
- Missing baseline does not suppress serious rule alerts.
- Test fixtures produce predictable risk levels.

---

### Phase 12 — Reporting and dashboard

#### Objective

Provide managerial visibility without depending on a custom dashboard framework.

#### Deliverables

- Graph view
- Pivot view
- Search filters and favorites
- Cashier and category analysis
- Optional kanban summary

#### Acceptance criteria

- Reports respect multi-company rules.
- Exposure totals use the correct currency context.
- Managers can analyze confirmed issues separately from false positives.
- No custom OWL dashboard is started until standard reports are accepted.

---

### Phase 13 — Isolation Forest enhancement

#### Objective

Detect multivariate patterns that fixed thresholds and single-feature statistics may miss.

#### Deliverables

- Optional Scikit-learn dependency
- Training dataset builder
- Model metadata/version storage
- Training scheduled action
- Model scoring service
- Graceful fallback when no valid model exists

#### Acceptance criteria

- Base addon still works when ML is disabled.
- Model never crosses company boundaries.
- Training and scoring features use the same schema and order.
- Model version used for a case is recorded.
- The result is explained through feature deviations.
- Evaluation compares rule-only, statistical and ML-assisted results.

---

### Phase 14 — Demonstration data and evaluation

#### Objective

Prepare a defensible academic and product demonstration.

#### Deliverables

- Anonymized or synthetic normal transaction data
- Injected abnormal scenarios
- Repeatable test/demo script
- Evaluation report

#### Required scenarios

1. Normal sale with ordinary discount
2. Accidental excessive discount
3. Large downward price override
4. Price below cost when cost is available
5. Multiple deleted high-value lines
6. Valid linked refund
7. High-value unlinked refund
8. Repeated refunds in a short window
9. Behaviour unusual for cashier but normal for store
10. Valid business exception classified by manager

#### Metrics

- Precision among generated top-risk cases
- False alerts per 1,000 analyzed transactions
- Manager-accepted alert percentage
- Confirmed issue distribution
- Average analysis time per order
- Manual review workload reduction estimate
- Financial exposure identified
- Rule-only versus hybrid results

---

### Phase 15 — Hardening and release

#### Objective

Prepare the addon for final demonstration and controlled deployment.

#### Deliverables

- Complete automated test suite
- Security review
- Performance test with at least 10,000 representative orders
- Installation and configuration guide
- Manager user guide
- Technical architecture documentation
- Known limitations
- Upgrade/uninstall verification

#### Exit criteria

- All must-have functional requirements pass.
- No critical access-control issue remains.
- POS sale and refund regression flows pass.
- Scheduled jobs are idempotent.
- Demonstration can be executed from documented steps.

---

## 23. Test strategy

### 23.1 Unit tests

- Every rule evaluator
- Risk-score normalization
- Financial-exposure calculations
- Baseline selection
- Z-score and zero-deviation handling
- Fingerprint generation
- Workflow transition validation

### 23.2 ORM and security tests

- Access rights for each group
- Multi-company record rules
- Cashier access denial
- Manager review permissions
- Administrator configuration permissions

### 23.3 Integration tests

```text
Create POS order
→ mark pending
→ run analysis
→ create case and reasons
→ create activity
→ manager reviews case
→ save feedback
→ reports include outcome
```

### 23.4 Regression tests

- Ordinary POS sale
- Discounted sale
- Refund through standard Odoo flow
- Offline order synchronization
- Session closing
- Module disabled for POS
- Module upgrade with existing orders

### 23.5 Performance tests

- Analyze 100 orders in one batch.
- Analyze historical data for at least 10,000 orders.
- Verify absence of query explosion.
- Confirm event synchronization payload remains reasonably small.

---

## 24. Definition of done for every feature

A feature is complete only when all applicable items are satisfied:

- Implementation follows current Odoo 19 source and conventions.
- Security access and record rules are defined.
- Views are usable and labels are understandable.
- Automated positive and negative tests are included.
- Existing tests pass.
- Addon installs and upgrades successfully.
- No unrelated code is changed.
- No core Odoo file is modified.
- Edge cases and limitations are documented.
- Acceptance criteria are demonstrated.
- The implementation phase checklist is updated.

---

## 25. Instructions to Claude

Claude must follow these instructions while implementing the project.

### 25.1 Before changing code

1. Read this entire PRD.
2. Read repository-level and nearest-directory `AGENTS.md` or equivalent instructions.
3. Inspect the existing repository and current git status.
4. Verify all referenced Odoo 19 model fields and frontend extension points against the installed source.
5. State which single phase and feature will be implemented.
6. Identify files expected to change.
7. Ask only questions that materially block the selected feature.

### 25.2 During implementation

- Implement only the requested phase or feature.
- Do not silently add later-phase functionality.
- Preserve unrelated user changes.
- Prefer model inheritance and supported patches over copying core code.
- Do not edit Odoo core files.
- Do not use arbitrary `safe_eval` rule expressions.
- Do not put heavy analysis in the POS payment request.
- Do not add a new dependency without explaining and receiving approval.
- Keep commits or change sets logically scoped if version-control actions are requested.
- Use clear field names and translatable user-facing strings.

### 25.3 After implementation

Report:

1. What was implemented
2. Files changed
3. Data models and fields added
4. Security behaviour
5. Tests added and their results
6. Manual verification steps
7. Known limitations
8. Exact next feature recommended by this PRD

Do not claim completion if tests were not run. State the reason when a test cannot be executed.

### 25.4 Required implementation prompt pattern

Use this pattern for each new Claude implementation session:

```text
Read Odoo-19-POS-Risk-Monitor-PRD.md completely.

Implement only Phase <number>: <phase name>, specifically:
- <feature one>
- <feature two>

First inspect the repository and Odoo 19 source. Then provide a brief implementation plan.
Do not implement later phases or add unapproved dependencies.
Add automated tests for the acceptance criteria.
Run the relevant tests and report the exact results.
```

---

## 26. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Manual price change cannot be distinguished from pricelist calculation | Capture applicable original price and explicit manual-override flag in POS frontend |
| Deleted lines disappear before backend synchronization | Store lightweight `pos.risk.event` records with UUID idempotency |
| Analysis delays checkout | Process completed orders asynchronously through scheduled batches |
| Too many false alerts | Conservative defaults, baselines, case thresholds and manager feedback |
| Insufficient cashier history | Fall back to POS and company baselines |
| No confirmed fraud labels | Use rules, statistical anomalies and unsupervised learning; evaluate reviewer acceptance |
| Employee accused incorrectly | Use risk language and require human investigation |
| Duplicate cases during retries | Deterministic fingerprint and unique constraint |
| ML dependency unavailable | Keep ML optional and preserve deterministic analysis |
| Multi-company data leakage | Company fields, record rules and security tests |
| Odoo 16 assumptions used in Odoo 19 | Verify fields and extension points from installed Odoo 19 source before every integration |

---

## 27. Open decisions to resolve during Phase 0

These decisions must be confirmed from the actual environment rather than guessed:

1. Odoo 19 Community or Enterprise edition
2. Exact custom addon repository and namespace conventions
3. Whether cashier identity uses only `pos.order.user_id` or an employee-based POS extension
4. Available test framework and CI commands
5. Whether POS event synchronization should extend the order payload or call a separate authenticated model method
6. How responsible risk managers are configured per POS/company
7. Deployment environment and permission to install Scikit-learn
8. Currency strategy for cross-company reporting
9. Data-retention period for event and case records
10. Whether cancelled unpaid orders are synchronized sufficiently for cancellation monitoring

These open decisions do not block Phases 1–3 unless they directly affect repository setup or security design.

---

## 28. Final release acceptance criteria

The semester project is complete when a reviewer can demonstrate the following sequence:

1. Enable monitoring for an Odoo 19 POS configuration.
2. Configure at least one rule in each primary category.
3. Complete normal and abnormal POS transactions.
4. Capture manual override and deletion events.
5. Analyze completed transactions in the backend.
6. Generate correct risk scores and levels.
7. Create explainable risk cases without duplicates.
8. Notify an authorized manager for a high-risk case.
9. Review and classify a case.
10. View the reviewed outcome in analytical reports.
11. Compare a transaction with an applicable behavioural baseline.
12. Demonstrate that ordinary POS operation still works when monitoring is disabled or analysis is temporarily unavailable.

The ML enhancement strengthens the research contribution but must not be allowed to prevent delivery of the complete rule-based and statistically contextualized product.