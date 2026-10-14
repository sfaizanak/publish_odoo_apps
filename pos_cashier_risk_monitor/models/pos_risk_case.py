# -*- coding: utf-8 -*-
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


CASE_CLASSIFICATIONS = [
    ("possible_error", "Possible Error"),
    ("policy_violation", "Policy Violation"),
    ("behavioural_anomaly", "Behavioural Anomaly"),
    ("fraud_risk", "Fraud Risk"),
    ("requires_review", "Requires Review"),
]
REVIEW_OUTCOMES = [
    ("cashier_mistake", "Cashier Mistake"),
    ("policy_violation", "Policy Violation"),
    ("training_required", "Training Required"),
    ("suspicious_activity", "Suspicious Activity"),
    ("configuration_issue", "Configuration Issue"),
    ("valid_business_operation", "Valid Business Operation"),
    ("false_positive", "False Positive"),
    ("duplicate", "Duplicate"),
]
STATE_SELECTION = [
    ("new", "New"),
    ("under_review", "Under Review"),
    ("resolved", "Resolved"),
    ("closed", "Closed"),
]
RISK_LEVEL_SELECTION = [
    ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"),
]
CATEGORY_SELECTION = [
    ("discount", "Discount"), ("price_override", "Price Override"),
    ("deletion", "Deletion"), ("cancellation", "Cancellation"),
    ("refund", "Refund"), ("timing", "Timing"), ("combined", "Combined"),
]


class PosRiskCase(models.Model):
    _name = "pos.risk.case"
    _description = "POS Risk Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "detected_at desc, id desc"

    _fingerprint_unique = models.Constraint(
        "unique(fingerprint)",
        "A risk case with this fingerprint already exists.",
    )

    name = fields.Char(string="Case Number", required=True, copy=False,
                       readonly=True, default=lambda self: _("New"), tracking=True)
    active = fields.Boolean(default=True)
    fingerprint = fields.Char(required=True, copy=False, index=True,
                              default=lambda self: str(uuid4()))
    company_id = fields.Many2one("res.company", required=True, index=True,
                                 default=lambda self: self.env.company)
    order_id = fields.Many2one("pos.order", required=True, index=True, ondelete="restrict")
    order_line_id = fields.Many2one("pos.order.line", ondelete="set null")
    cashier_id = fields.Many2one("res.users", index=True)
    session_id = fields.Many2one("pos.session", index=True)
    config_id = fields.Many2one("pos.config", index=True)
    category = fields.Selection(CATEGORY_SELECTION, required=True, index=True)
    classification = fields.Selection(CASE_CLASSIFICATIONS, required=True,
                                       default="requires_review", tracking=True)
    rule_score = fields.Float(default=0.0)
    anomaly_score = fields.Float(default=0.0)
    impact_score = fields.Float(default=0.0)
    risk_score = fields.Float(default=0.0, index=True, tracking=True)
    risk_level = fields.Selection(RISK_LEVEL_SELECTION, required=True,
                                  default="low", index=True, tracking=True)
    currency_id = fields.Many2one("res.currency", required=True,
                                  default=lambda self: self.env.company.currency_id)
    financial_exposure = fields.Monetary(currency_field="currency_id", default=0.0)
    explanation = fields.Text()
    recommended_action = fields.Text()
    state = fields.Selection(STATE_SELECTION, required=True, default="new",
                             index=True, tracking=True)
    assigned_user_id = fields.Many2one("res.users", tracking=True)
    reviewed_by = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    review_outcome = fields.Selection(REVIEW_OUTCOMES, tracking=True)
    review_notes = fields.Text()
    detected_at = fields.Datetime(required=True, default=fields.Datetime.now,
                                  index=True, readonly=True)
    model_version = fields.Char()
    reason_ids = fields.One2many("pos.risk.case.reason", "case_id",
                                 string="Reasons", copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pos.risk.case") or _("New")
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("currency_id", self.env.company.currency_id.id)
        return super().create(vals_list)

    def _risk_notification_users(self):
        self.ensure_one()
        if self.company_id.pos_risk_manager_ids:
            return self.company_id.pos_risk_manager_ids
        group = self.env.ref(
            "pos_cashier_risk_monitor.group_pos_risk_manager", raise_if_not_found=False
        )
        if not group:
            return self.env["res.users"]
        return self.env["res.users"].search([
            ("group_ids", "in", group.id),
            ("company_ids", "in", self.company_id.id),
        ])

    def _risk_notify_stakeholders(self):
        Activity = self.env["mail.activity"].sudo()
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for case in self:
            company = case.company_id
            notify = (
                case.risk_level in ("high", "critical")
                and company.pos_risk_create_activity_high
            )
            if not notify or not activity_type:
                continue
            users = case._risk_notification_users()
            summary = _("Review POS risk case %s") % case.name
            note = _(
                "Risk level: %(level)s\nScore: %(score).2f\nOrder: %(order)s\n"
                "Cashier: %(cashier)s\nExposure: %(exposure)s\n\n%(explanation)s"
            ) % {
                "level": case.risk_level.title(),
                "score": case.risk_score,
                "order": case.order_id.display_name,
                "cashier": case.cashier_id.display_name,
                "exposure": "%.2f %s" % (
                    case.financial_exposure, case.currency_id.name or ""
                ),
                "explanation": case.explanation or "",
            }
            model_id = self.env["ir.model"]._get_id("pos.risk.case")
            for user in users:
                existing = Activity.search([
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", case.id),
                    ("user_id", "=", user.id),
                    ("summary", "=", summary),
                ], limit=1)
                if not existing:
                    Activity.create({
                        "activity_type_id": activity_type.id,
                        "res_model_id": model_id,
                        "res_id": case.id,
                        "user_id": user.id,
                        "summary": summary,
                        "note": note,
                        "date_deadline": fields.Date.context_today(case),
                    })
            if case.risk_level == "critical" and company.pos_risk_notify_critical:
                marker = _("Critical POS risk notification")
                if not self.env["mail.message"].sudo().search_count([
                    ("model", "=", "pos.risk.case"),
                    ("res_id", "=", case.id),
                    ("subject", "=", marker),
                ]):
                    partners = users.mapped("partner_id")
                    case.sudo().message_post(
                        subject=marker,
                        body=note,
                        partner_ids=partners.ids,
                    )
        return True

    @api.constrains("risk_score", "rule_score", "anomaly_score", "impact_score")
    def _check_scores(self):
        for case in self:
            for field_name in ("risk_score", "rule_score", "anomaly_score", "impact_score"):
                value = getattr(case, field_name)
                if not 0 <= value <= 100:
                    raise ValidationError(
                        _("%s must be between 0 and 100.") %
                        field_name.replace("_", " ").title()
                    )

    @api.constrains("review_outcome", "review_notes")
    def _check_review_notes(self):
        required = {
            "cashier_mistake", "policy_violation", "training_required",
            "suspicious_activity", "configuration_issue",
        }
        labels = dict(REVIEW_OUTCOMES)
        for case in self:
            if case.review_outcome in required and not (case.review_notes or "").strip():
                raise ValidationError(
                    _("Review notes are required for outcome '%s'.") %
                    labels.get(case.review_outcome)
                )

    def _require_manager(self):
        if not self.env.user.has_group(
            "pos_cashier_risk_monitor.group_pos_risk_manager"
        ):
            raise UserError(_("Only a risk manager can change a case workflow."))

    def action_start_review(self):
        self._require_manager()
        if any(case.state != "new" for case in self):
            raise UserError(_("Only new cases can be moved to Under Review."))
        self.write({"state": "under_review", "assigned_user_id": self.env.user.id})
        self.message_post(body=_("Investigation started by %s.") %
                          self.env.user.display_name)
        return True

    def action_resolve(self):
        self._require_manager()
        if any(case.state != "under_review" for case in self):
            raise UserError(_("Only cases under review can be resolved."))
        if any(not case.review_outcome for case in self):
            raise UserError(_("Select a review outcome before resolving the case."))
        self.write({
            "state": "resolved",
            "reviewed_by": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        })
        self.message_post(body=_("Case resolved by %s.") % self.env.user.display_name)
        return True

    def action_close(self):
        self._require_manager()
        if any(case.state != "resolved" for case in self):
            raise UserError(_("Only resolved cases can be closed."))
        self.write({"state": "closed"})
        self.message_post(body=_("Case closed by %s.") % self.env.user.display_name)
        return True

    def action_close_duplicate(self):
        self._require_manager()
        if any(case.state != "new" or case.review_outcome != "duplicate" for case in self):
            raise UserError(
                _("Only new cases explicitly marked as duplicate can be closed directly.")
            )
        self.write({
            "state": "closed",
            "reviewed_by": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        })
        self.message_post(body=_("Duplicate case closed by %s.") %
                          self.env.user.display_name)
        return True

    def action_reopen(self):
        self._require_manager()
        if any(case.state != "closed" for case in self):
            raise UserError(_("Only closed cases can be reopened."))
        self.write({
            "state": "under_review",
            "reviewed_by": False,
            "reviewed_at": False,
        })
        self.message_post(body=_("Case reopened by %s.") % self.env.user.display_name)
        return True


class PosRiskCaseReason(models.Model):
    _name = "pos.risk.case.reason"
    _description = "POS Risk Case Reason"
    _order = "sequence, id"

    case_id = fields.Many2one("pos.risk.case", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="case_id.company_id", store=True, index=True)
    rule_id = fields.Many2one("pos.risk.rule", ondelete="set null")
    reason_code = fields.Char(required=True)
    description = fields.Text(required=True)
    observed_value = fields.Float()
    expected_value = fields.Float()
    deviation_value = fields.Float()
    contribution_score = fields.Float()
    currency_id = fields.Many2one(related="case_id.currency_id", store=True)
    financial_exposure = fields.Monetary(currency_field="currency_id")
    sequence = fields.Integer(default=10)

    @api.constrains("contribution_score")
    def _check_contribution_score(self):
        for reason in self:
            if not 0 <= reason.contribution_score <= 100:
                raise ValidationError(_("Contribution score must be between 0 and 100."))
