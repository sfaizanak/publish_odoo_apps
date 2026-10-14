# -*- coding: utf-8 -*-
from odoo import fields, models


EVENT_TYPES = [
    ("discount_applied", "Discount Applied"),
    ("price_overridden", "Price Overridden"),
    ("line_deleted", "Line Deleted"),
    ("quantity_changed", "Quantity Changed"),
    ("refund_started", "Refund Started"),
    ("order_cancelled", "Order Cancelled"),
    ("payment_cancelled", "Payment Cancelled"),
]


class PosRiskEvent(models.Model):
    _name = "pos.risk.event"
    _description = "POS Risk Event"
    _order = "event_at desc, id desc"

    _event_uuid_unique = models.Constraint(
        "unique (event_uuid)",
        "A POS risk event with this UUID already exists.",
    )

    name = fields.Char(required=True)
    event_uuid = fields.Char(required=True, copy=False, index=True)
    order_uuid = fields.Char(required=True, index=True)
    order_id = fields.Many2one("pos.order", index=True, ondelete="set null")
    order_line_uuid = fields.Char(index=True)
    order_line_id = fields.Many2one("pos.order.line", index=True, ondelete="set null")
    cashier_id = fields.Many2one("res.users", index=True)
    session_id = fields.Many2one("pos.session", index=True)
    config_id = fields.Many2one("pos.config", index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    product_id = fields.Many2one("product.product", ondelete="set null")
    event_type = fields.Selection(EVENT_TYPES, required=True, index=True)
    old_numeric_value = fields.Float()
    new_numeric_value = fields.Float()
    quantity = fields.Float()
    currency_id = fields.Many2one("res.currency")
    event_at = fields.Datetime(required=True, index=True)
    server_received_at = fields.Datetime(required=True, default=fields.Datetime.now)
    reason = fields.Char()
    metadata_json = fields.Json()
    processed = fields.Boolean(default=False, index=True)

    def _compute_display_name(self):
        for event in self:
            event.display_name = "%s - %s" % (event.name, event.event_type)
