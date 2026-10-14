# -*- coding: utf-8 -*-
import logging
import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .pos_risk_event import EVENT_TYPES

_logger = logging.getLogger(__name__)

ANALYSIS_STATES = [
    ("not_required", "Not Required"),
    ("pending", "Pending"),
    ("processing", "Processing"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]
RISK_LEVELS = [
    ("none", "None"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class PosOrder(models.Model):
    _inherit = "pos.order"

    risk_analysis_state = fields.Selection(
        ANALYSIS_STATES, default="not_required", index=True, copy=False,
        readonly=True, tracking=True,
    )
    risk_score = fields.Float(default=0.0, copy=False, readonly=True)
    risk_level = fields.Selection(
        RISK_LEVELS, default="none", index=True, copy=False, readonly=True,
    )
    risk_case_count = fields.Integer(
        compute="_compute_risk_case_count", string="Risk Cases",
    )
    risk_analyzed_at = fields.Datetime(copy=False, readonly=True)
    risk_analysis_error = fields.Text(copy=False, readonly=True)
    risk_case_ids = fields.One2many(
        "pos.risk.case",
        "order_id",
        string="Related Risk Cases",
        readonly=True,
        groups="pos_cashier_risk_monitor.group_pos_risk_user",
    )
    def _compute_risk_case_count(self):
        for order in self:
            # POS cashiers must not be granted read access to risk cases just
            # because an order form computes this counter.  Count internally
            # with elevated read access and expose only the number.
            order.risk_case_count = self.env["pos.risk.case"].sudo().search_count([
                ("order_id", "=", order.id),
            ])

    def _risk_monitoring_enabled(self):
        self.ensure_one()
        return bool(self.config_id.pos_risk_monitoring_enabled)

    def _risk_mark_analysis_pending(self):
        for order in self:
            if order.config_id.pos_risk_monitoring_enabled:
                order.with_context(skip_risk_state_mark=True).write({
                    "risk_analysis_state": "pending",
                    "risk_analysis_error": False,
                })
            else:
                order.with_context(skip_risk_state_mark=True).write({
                    "risk_analysis_state": "not_required",
                    "risk_analysis_error": False,
                })
        return True

    def _risk_require_admin(self):
        if not self.env.user.has_group(
            "pos_cashier_risk_monitor.group_pos_risk_admin"
        ):
            raise AccessError(_("Only risk administrators can trigger analysis."))

    def action_risk_analyze(self):
        self._risk_require_admin()
        self._risk_mark_analysis_pending()
        self._risk_run_analysis()
        return True

    def action_risk_retry_analysis(self):
        self._risk_require_admin()
        failed = self.filtered(lambda order: order.risk_analysis_state == "failed")
        if not failed:
            raise AccessError(_("Only failed risk analyses can be retried."))
        failed._risk_mark_analysis_pending()
        failed._risk_run_analysis()
        return True

    def write(self, vals):
        result = super().write(vals)
        if (
            not self.env.context.get("skip_risk_state_mark")
            and vals.get("state") in ("paid", "done")
        ):
            self._risk_mark_analysis_pending()
        return result

    def _process_saved_order(self, draft):
        result = super()._process_saved_order(draft)
        if not draft:
            self._risk_mark_analysis_pending()
        return result

    @api.model
    def _process_order(self, order, existing_order):
        payload = order.pop("risk_event_payload", []) if isinstance(order, dict) else []
        result = super()._process_order(order, existing_order)
        pos_order = self.browse(result)
        if payload:
            pos_order._risk_reconcile_events(payload)
        return result

    def _risk_reconcile_events(self, payload):
        # POS users are allowed to submit events but are intentionally not
        # allowed to browse historical risk events.
        Event = self.env["pos.risk.event"].sudo()
        event_labels = dict(EVENT_TYPES)
        for raw_event in payload:
            try:
                if not isinstance(raw_event, dict):
                    continue
                event_uuid = raw_event.get("event_uuid")
                event_type = raw_event.get("event_type")
                if (
                    not isinstance(event_uuid, str)
                    or not event_uuid
                    or event_type not in event_labels
                    or Event.search_count([("event_uuid", "=", event_uuid)])
                ):
                    continue

                def finite_number(value, default=0.0):
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        return default
                    return value if math.isfinite(value) else default

                line = self.lines.filtered(
                    lambda candidate: candidate.uuid == raw_event.get("order_line_uuid")
                )[:1]
                old_value = finite_number(raw_event.get("old_numeric_value"))
                new_value = finite_number(raw_event.get("new_numeric_value"))
                if event_type == "price_overridden" and line:
                    new_value = line.price_unit
                    line._risk_record_price_override(old_value, str(raw_event.get("reason", ""))[:255])

                event_at = fields.Datetime.to_datetime(raw_event.get("event_at"))
                if not event_at:
                    event_at = fields.Datetime.now()

                values = {
                    "name": event_labels[event_type],
                    "event_uuid": event_uuid[:128],
                    "order_uuid": self.uuid,
                    "order_id": self.id,
                    "order_line_uuid": line.uuid if line else raw_event.get("order_line_uuid"),
                    "order_line_id": line.id if line else False,
                    "cashier_id": self.user_id.id,
                    "session_id": self.session_id.id,
                    "config_id": self.config_id.id,
                    "company_id": self.company_id.id,
                    "product_id": line.product_id.id if line else False,
                    "event_type": event_type,
                    "old_numeric_value": old_value,
                    "new_numeric_value": new_value,
                    "quantity": finite_number(raw_event.get("quantity")),
                    "currency_id": self.currency_id.id,
                    "event_at": event_at,
                    "reason": str(raw_event.get("reason", ""))[:255],
                    "metadata_json": {"source": "pos_frontend"},
                }
                with self.env.cr.savepoint():
                    Event.create(values)
            except Exception:
                _logger.warning(
                    "Ignoring malformed POS risk event for order %s",
                    self.display_name, exc_info=True,
                )
        return True


    def action_view_risk_cases(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Risk Cases"),
            "res_model": "pos.risk.case",
            "view_mode": "list,form",
            "domain": [("order_id", "=", self.id)],
        }


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    risk_original_unit_price = fields.Float(copy=False, readonly=True)
    risk_is_manual_price_override = fields.Boolean(copy=False, readonly=True)
    risk_price_override_difference = fields.Float(copy=False, readonly=True)
    risk_price_override_percentage = fields.Float(copy=False, readonly=True)
    risk_price_override_reason = fields.Char(copy=False)
    risk_manual_price_change_count = fields.Integer(copy=False, readonly=True)

    def _risk_record_price_override(self, previous_price, reason=""):
        for line in self:
            original = line.risk_original_unit_price or previous_price
            difference = line.price_unit - original
            percentage = abs(difference / original * 100) if original else 0.0
            line.with_context(skip_risk_state_mark=True).write({
                "risk_original_unit_price": original,
                "risk_is_manual_price_override": True,
                "risk_price_override_difference": difference,
                "risk_price_override_percentage": percentage,
                "risk_manual_price_change_count": line.risk_manual_price_change_count + 1,
                "risk_price_override_reason": reason,
            })

    @api.model
    def _load_pos_data_fields(self, config):
        fields_to_load = super()._load_pos_data_fields(config)
        for field_name in (
            "risk_original_unit_price",
            "risk_is_manual_price_override",
            "risk_price_override_difference",
            "risk_price_override_percentage",
            "risk_manual_price_change_count",
        ):
            if field_name not in fields_to_load:
                fields_to_load.append(field_name)
        return fields_to_load




