# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

WEIGHT_SUM_TOLERANCE = 0.01


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_risk_case_creation_threshold = fields.Float(string="Case-Creation Score Threshold", default=40.0)
    pos_risk_high_threshold = fields.Float(string="High-Risk Threshold", default=70.0)
    pos_risk_critical_threshold = fields.Float(string="Critical-Risk Threshold", default=85.0)
    pos_risk_baseline_min_sample = fields.Integer(string="Minimum Cashier Baseline Sample", default=30)
    pos_risk_baseline_lookback_days = fields.Integer(string="Baseline Lookback Days", default=90)
    pos_risk_create_activity_high = fields.Boolean(string="Create Activity for High-Risk Case", default=True)
    pos_risk_notify_critical = fields.Boolean(string="Notify for Critical Cases", default=True)
    pos_risk_manager_ids = fields.Many2many(
        "res.users",
        "res_company_pos_risk_manager_rel",
        "company_id",
        "user_id",
        string="POS Risk Managers",
        help="Users who receive high and critical POS risk activities. Leave empty to use Risk Managers.",
    )
    pos_risk_require_price_change_reason = fields.Boolean(string="Require Manual Price-Change Reason", default=False)
    pos_risk_rule_score_weight = fields.Float(string="Rule-Score Weight", default=0.45)
    pos_risk_anomaly_score_weight = fields.Float(string="Anomaly-Score Weight", default=0.35)
    pos_risk_impact_score_weight = fields.Float(string="Impact-Score Weight", default=0.20)
    pos_risk_ml_enabled = fields.Boolean(
        string="Enable Isolation Forest", default=False,
        help="Use optional unsupervised anomaly scoring after a model is trained.",
    )
    pos_risk_ml_lookback_days = fields.Integer(
        string="ML Training Lookback Days", default=90,
    )

    @api.constrains(
        "pos_risk_rule_score_weight",
        "pos_risk_anomaly_score_weight",
        "pos_risk_impact_score_weight",
    )
    def _check_pos_risk_score_weights(self):
        for company in self:
            weights = (
                company.pos_risk_rule_score_weight,
                company.pos_risk_anomaly_score_weight,
                company.pos_risk_impact_score_weight,
            )
            if any(weight < 0 for weight in weights):
                raise ValidationError(_("Risk-score weights cannot be negative."))
            total = sum(weights)
            if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
                raise ValidationError(
                    _("The rule-score, anomaly-score and impact-score weights "
                      "must add up to 1.0 (currently %.3f) for company '%s'.")
                    % (total, company.name)
                )

    @api.constrains(
        "pos_risk_case_creation_threshold",
        "pos_risk_high_threshold",
        "pos_risk_critical_threshold",
    )
    def _check_pos_risk_thresholds(self):
        labels = {
            "pos_risk_case_creation_threshold": _("Case-creation threshold"),
            "pos_risk_high_threshold": _("High-risk threshold"),
            "pos_risk_critical_threshold": _("Critical-risk threshold"),
        }
        for company in self:
            for field_name, label in labels.items():
                value = getattr(company, field_name)
                if not 0 <= value <= 100:
                    raise ValidationError(_("%s must be between 0 and 100 (got %.2f).") % (label, value))
            if not (
                company.pos_risk_case_creation_threshold
                <= company.pos_risk_high_threshold
                <= company.pos_risk_critical_threshold
            ):
                raise ValidationError(
                    _("Risk thresholds must be ordered: case-creation threshold "
                      "<= high-risk threshold <= critical-risk threshold.")
                )

    @api.constrains("pos_risk_baseline_min_sample", "pos_risk_baseline_lookback_days")
    def _check_pos_risk_baseline_settings(self):
        for company in self:
            if company.pos_risk_baseline_min_sample < 1:
                raise ValidationError(_("Minimum cashier baseline sample must be at least 1."))
            if company.pos_risk_baseline_lookback_days < 1:
                raise ValidationError(_("Baseline lookback days must be at least 1."))

    @api.constrains("pos_risk_ml_lookback_days")
    def _check_pos_risk_ml_settings(self):
        for company in self:
            if company.pos_risk_ml_lookback_days < 1:
                raise ValidationError(_("ML training lookback days must be at least 1."))
