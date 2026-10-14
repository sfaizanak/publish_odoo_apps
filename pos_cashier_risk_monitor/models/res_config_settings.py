# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Phase 2 scope: expose the company-wide risk policy settings from
    PRD §10, except "Enable POS risk monitoring" and "Analyze completed
    orders automatically", which are per-POS and live on pos.config
    (Phase 1's view is reused/extended rather than duplicated here).
    """
    _inherit = "res.config.settings"

    pos_risk_case_creation_threshold = fields.Float(
        related="company_id.pos_risk_case_creation_threshold", readonly=False
    )
    pos_risk_high_threshold = fields.Float(
        related="company_id.pos_risk_high_threshold", readonly=False
    )
    pos_risk_critical_threshold = fields.Float(
        related="company_id.pos_risk_critical_threshold", readonly=False
    )
    pos_risk_baseline_min_sample = fields.Integer(
        related="company_id.pos_risk_baseline_min_sample", readonly=False
    )
    pos_risk_baseline_lookback_days = fields.Integer(
        related="company_id.pos_risk_baseline_lookback_days", readonly=False
    )
    pos_risk_create_activity_high = fields.Boolean(
        related="company_id.pos_risk_create_activity_high", readonly=False
    )
    pos_risk_notify_critical = fields.Boolean(
        related="company_id.pos_risk_notify_critical", readonly=False
    )
    pos_risk_manager_ids = fields.Many2many(
        related="company_id.pos_risk_manager_ids", readonly=False
    )
    pos_risk_require_price_change_reason = fields.Boolean(
        related="company_id.pos_risk_require_price_change_reason", readonly=False
    )
    pos_risk_rule_score_weight = fields.Float(
        related="company_id.pos_risk_rule_score_weight", readonly=False
    )
    pos_risk_anomaly_score_weight = fields.Float(
        related="company_id.pos_risk_anomaly_score_weight", readonly=False
    )
    pos_risk_impact_score_weight = fields.Float(
        related="company_id.pos_risk_impact_score_weight", readonly=False
    )
    pos_risk_ml_enabled = fields.Boolean(
        related="company_id.pos_risk_ml_enabled", readonly=False
    )
    pos_risk_ml_lookback_days = fields.Integer(
        related="company_id.pos_risk_ml_lookback_days", readonly=False
    )
