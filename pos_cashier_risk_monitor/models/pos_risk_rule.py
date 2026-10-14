# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# PRD §9.4: "Safe supported operators only; never execute arbitrary Python
# expressions." This selection is the entire whitelist. Nothing in this
# module ever calls eval()/exec() on rule configuration — the mapping from
# these codes to an actual comparison is a Phase 7 concern (the "explicit
# registry of supported rule evaluators" the PRD calls for).
OPERATOR_SELECTION = [
    ("gte", ">="),
    ("gt", ">"),
    ("lte", "<="),
    ("lt", "<"),
    ("eq", "="),
    ("neq", "≠"),
]

CATEGORY_SELECTION = [
    ("discount", "Discount"),
    ("price_override", "Price Override"),
    ("deletion", "Deletion"),
    ("cancellation", "Cancellation"),
    ("refund", "Refund"),
    ("timing", "Timing"),
    ("combined", "Combined"),
]

SCOPE_SELECTION = [
    ("order", "Order"),
    ("line", "Order Line"),
    ("event", "Captured Event"),
    ("cashier_window", "Cashier Rolling Window"),
]

# Kept identical to the pos.risk.case classifications in PRD §9.6 so a
# rule's suggested classification lines up with the case it will one day
# help create (Phase 8).
CLASSIFICATION_SELECTION = [
    ("possible_error", "Possible Error"),
    ("policy_violation", "Policy Violation"),
    ("behavioural_anomaly", "Behavioural Anomaly"),
    ("fraud_risk", "Fraud Risk"),
    ("requires_review", "Requires Review"),
]


class PosRiskRule(models.Model):
    _name = "pos.risk.rule"
    _description = "POS Risk Monitoring Rule"
    _order = "category, severity_score desc, name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        copy=False,
        help="Stable technical identifier. Cannot be changed after the "
             "rule is created — archive and recreate instead.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        help="Leave empty to share this rule across every company.",
    )
    config_ids = fields.Many2many(
        "pos.config",
        "pos_risk_rule_pos_config_rel",
        "rule_id",
        "config_id",
        string="Limit to POS(s)",
        help="Leave empty to apply this rule to every point of sale.",
    )
    category = fields.Selection(CATEGORY_SELECTION, required=True)
    scope = fields.Selection(SCOPE_SELECTION, required=True)
    operator = fields.Selection(
        OPERATOR_SELECTION,
        required=True,
        default="gte",
        help="Whitelisted comparison only. Rule logic can never be stored "
             "or executed as arbitrary code.",
    )
    threshold_value = fields.Float(
        required=True,
        default=0.0,
        help="Primary comparison value. For rules whose real condition is "
             "an amount, see Minimum Amount instead — this field is still "
             "required but may be a placeholder for those rules.",
    )
    secondary_threshold_value = fields.Float(
        help="Optional secondary value for range/window comparisons."
    )
    window_minutes = fields.Integer(
        string="Window (minutes)",
        default=0,
        help="Rolling window for frequency-based rules. 0 means not "
             "applicable to this rule.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        help="Technical field so Minimum Amount can render with the "
             "correct currency.",
    )
    minimum_amount = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        help="Ignore financially insignificant activity below this "
             "amount. Demonstration defaults must be reviewed per company "
             "and currency before activation.",
    )
    severity_score = fields.Float(
        required=True,
        default=50.0,
        help="0–100. How serious a single trigger of this rule is.",
    )
    risk_weight = fields.Float(
        required=True,
        default=1.0,
        help="Non-negative weighting applied when this rule contributes "
             "to a case's combined score.",
    )
    case_classification = fields.Selection(
        CLASSIFICATION_SELECTION,
        string="Suggested Classification",
        help="Suggested pos.risk.case classification when this rule "
             "triggers. A reviewer can always change it on the case.",
    )
    description = fields.Text(help="Business explanation of what this rule detects.")
    recommended_action = fields.Text(help="Displayed on the generated case.")

    @api.depends("company_id")
    def _compute_currency_id(self):
        for rule in self:
            rule.currency_id = (
                rule.company_id.currency_id or self.env.company.currency_id
            )

    @api.constrains("severity_score")
    def _check_severity_score(self):
        for rule in self:
            if not (0 <= rule.severity_score <= 100):
                raise ValidationError(
                    _("Severity score for rule '%s' must be between 0 and 100.")
                    % rule.name
                )

    @api.constrains("risk_weight")
    def _check_risk_weight(self):
        for rule in self:
            if rule.risk_weight < 0:
                raise ValidationError(
                    _("Risk weight for rule '%s' cannot be negative.") % rule.name
                )

    @api.constrains("window_minutes")
    def _check_window_minutes(self):
        for rule in self:
            if rule.window_minutes < 0:
                raise ValidationError(
                    _("Window (minutes) for rule '%s' cannot be negative.")
                    % rule.name
                )

    @api.constrains("minimum_amount")
    def _check_minimum_amount(self):
        for rule in self:
            if rule.minimum_amount < 0:
                raise ValidationError(
                    _("Minimum amount for rule '%s' cannot be negative.")
                    % rule.name
                )

    @api.constrains("code", "company_id")
    def _check_code_scope_unique(self):
        for rule in self:
            if not rule.code:
                continue
            if rule.company_id:
                domain = [
                    ("id", "!=", rule.id),
                    ("code", "=", rule.code),
                    "|",
                    ("company_id", "=", rule.company_id.id),
                    ("company_id", "=", False),
                ]
            else:
                # A global rule's code must not collide with ANY other
                # rule's code, company-specific or global.
                domain = [
                    ("id", "!=", rule.id),
                    ("code", "=", rule.code),
                ]
            if self.with_context(active_test=False).search_count(domain):
                raise ValidationError(
                    _(
                        "Rule code '%s' is already used by another rule in "
                        "this company or in the global scope. Codes must be "
                        "unique per company or shared/global scope."
                    )
                    % rule.code
                )

    def write(self, vals):
        if "code" in vals:
            for rule in self:
                if rule.code and vals["code"] != rule.code:
                    raise UserError(
                        _(
                            "The code of rule '%s' cannot be changed once "
                            "created. Archive it and create a new rule "
                            "with the desired code instead."
                        )
                        % rule.name
                    )
        return super().write(vals)