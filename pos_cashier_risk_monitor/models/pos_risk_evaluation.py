# -*- coding: utf-8 -*-
"""Demo scenario catalog and lightweight evaluation metrics."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosRiskEvaluation(models.Model):
    _name = "pos.risk.evaluation"
    _description = "POS Risk Evaluation Run"
    _order = "run_at desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("Evaluation Run"))
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    run_at = fields.Datetime(readonly=True)
    scenario_ids = fields.One2many("pos.risk.evaluation.scenario", "evaluation_id")
    scenario_count = fields.Integer(compute="_compute_metrics")
    evaluated_count = fields.Integer(compute="_compute_metrics")
    true_positive = fields.Integer(compute="_compute_metrics")
    false_positive = fields.Integer(compute="_compute_metrics")
    false_negative = fields.Integer(compute="_compute_metrics")
    true_negative = fields.Integer(compute="_compute_metrics")
    precision = fields.Float(compute="_compute_metrics")
    false_alerts_per_1000 = fields.Float(compute="_compute_metrics")
    acceptance_rate = fields.Float(compute="_compute_metrics")
    total_exposure = fields.Monetary(compute="_compute_metrics")
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True
    )
    notes = fields.Text()

    @api.depends("scenario_ids", "scenario_ids.evaluated", "scenario_ids.predicted_alert")
    def _compute_metrics(self):
        for run in self:
            scenarios = run.scenario_ids
            evaluated = scenarios.filtered("evaluated")
            tp = sum(1 for s in evaluated if s.expected_alert and s.predicted_alert)
            fp = sum(1 for s in evaluated if not s.expected_alert and s.predicted_alert)
            fn = sum(1 for s in evaluated if s.expected_alert and not s.predicted_alert)
            tn = sum(1 for s in evaluated if not s.expected_alert and not s.predicted_alert)
            predicted_positive = tp + fp
            run.scenario_count = len(scenarios)
            run.evaluated_count = len(evaluated)
            run.true_positive = tp
            run.false_positive = fp
            run.false_negative = fn
            run.true_negative = tn
            run.precision = (tp / predicted_positive * 100.0) if predicted_positive else 0.0
            run.false_alerts_per_1000 = (fp / len(evaluated) * 1000.0) if evaluated else 0.0
            run.acceptance_rate = (
                (tp + tn) / len(evaluated) * 100.0 if evaluated else 0.0
            )
            run.total_exposure = sum(
                sum(scenario.order_id.risk_case_ids.mapped("financial_exposure"))
                for scenario in evaluated
                if scenario.order_id
            )

    def action_evaluate(self):
        for run in self:
            if not run.scenario_ids:
                raise UserError(_("Add at least one evaluation scenario first."))
            run.scenario_ids.action_evaluate()
            run.write({"run_at": fields.Datetime.now()})
        return True


class PosRiskEvaluationScenario(models.Model):
    _name = "pos.risk.evaluation.scenario"
    _description = "POS Risk Evaluation Scenario"
    _order = "sequence, id"

    _code_unique = models.Constraint(
        "unique(code, company_id)",
        "Evaluation scenario codes must be unique per company.",
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    evaluation_id = fields.Many2one("pos.risk.evaluation", ondelete="cascade", index=True)
    description = fields.Text(required=True)
    category = fields.Selection(
        [
            ("normal", "Normal Sale"),
            ("discount", "Discount"),
            ("price_override", "Price Override"),
            ("deletion", "Deletion"),
            ("refund", "Refund"),
            ("baseline", "Baseline Anomaly"),
            ("exception", "Valid Exception"),
        ],
        required=True,
    )
    expected_alert = fields.Boolean(string="Expected Alert")
    expected_outcome = fields.Selection(
        [("alert", "Should Alert"), ("no_alert", "Should Not Alert")],
        required=True,
        default="no_alert",
    )
    expected_level = fields.Selection(
        [("none", "None"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        required=True,
        default="none",
    )
    order_id = fields.Many2one("pos.order", ondelete="set null")
    predicted_alert = fields.Boolean(readonly=True)
    predicted_level = fields.Selection(
        [("none", "None"), ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        readonly=True,
    )
    observed_score = fields.Float(readonly=True)
    evaluated = fields.Boolean(readonly=True)
    evaluation_notes = fields.Text(readonly=True)

    @api.onchange("expected_alert")
    def _onchange_expected_alert(self):
        for scenario in self:
            scenario.expected_outcome = "alert" if scenario.expected_alert else "no_alert"

    def action_evaluate(self):
        for scenario in self:
            if not scenario.order_id:
                scenario.write({
                    "evaluated": False,
                    "evaluation_notes": _("No POS order is linked to this scenario."),
                })
                continue
            order = scenario.order_id
            predicted_alert = bool(order.risk_case_count)
            scenario.write({
                "predicted_alert": predicted_alert,
                "predicted_level": order.risk_level,
                "observed_score": order.risk_score,
                "evaluated": True,
                "evaluation_notes": _(
                    "Compared the linked POS order's risk score and case count with the expected scenario outcome."
                ),
            })
        return True
