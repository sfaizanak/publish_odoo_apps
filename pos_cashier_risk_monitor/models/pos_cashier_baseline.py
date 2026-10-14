# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosCashierBaseline(models.Model):
    _name = "pos.cashier.baseline"
    _description = "POS Cashier Behavioural Baseline"
    _order = "period_end desc, id desc"

    _subject_period_unique = models.Constraint(
        "unique(company_id, subject_key, period_start, period_end)",
        "Only one baseline is allowed for the same subject and period.",
    )

    name = fields.Char(required=True, readonly=True, default=lambda self: _("New"))
    active = fields.Boolean(default=True)
    subject_key = fields.Char(required=True, index=True, copy=False)
    cashier_id = fields.Many2one("res.users", index=True)
    config_id = fields.Many2one("pos.config", index=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    baseline_level = fields.Selection(
        [("cashier", "Cashier"), ("pos", "Point of Sale"), ("company", "Company")],
        required=True,
    )
    period_start = fields.Datetime(required=True, index=True)
    period_end = fields.Datetime(required=True, index=True)
    sample_count = fields.Integer(required=True, default=0)
    avg_discount_pct = fields.Float()
    std_discount_pct = fields.Float()
    p95_discount_pct = fields.Float()
    avg_price_override_pct = fields.Float()
    std_price_override_pct = fields.Float()
    avg_deleted_lines = fields.Float()
    p95_deleted_lines = fields.Float()
    avg_refund_amount = fields.Float()
    p95_refund_amount = fields.Float()
    refund_frequency = fields.Float()
    calculated_at = fields.Datetime(required=True, default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self._subject_name(vals)
        return super().create(vals_list)

    @api.model
    def _subject_name(self, vals):
        level = vals.get("baseline_level", "company")
        if level == "cashier" and vals.get("cashier_id"):
            return self.env["res.users"].browse(vals["cashier_id"]).display_name
        if level == "pos" and vals.get("config_id"):
            return self.env["pos.config"].browse(vals["config_id"]).display_name
        return self.env["res.company"].browse(
            vals.get("company_id", self.env.company.id)
        ).display_name

    @api.constrains("sample_count", "period_start", "period_end")
    def _check_period_and_sample(self):
        for baseline in self:
            if baseline.sample_count < 0:
                raise ValidationError(_("Baseline sample count cannot be negative."))
            if baseline.period_end <= baseline.period_start:
                raise ValidationError(_("Baseline period end must be after its start."))

    @api.model
    def _percentile(self, values, percentile):
        if not values:
            return 0.0
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @api.model
    def _statistics(self, orders):
        values = [order._risk_extract_features() for order in orders]
        discounts = [item["average_discount_pct"] for item in values]
        overrides = [item["max_price_deviation_pct"] for item in values]
        deleted = [item["deleted_line_count"] for item in values]
        refunds = [item["refund_amount"] for item in values]
        return {
            "sample_count": len(values),
            "avg_discount_pct": mean(discounts) if discounts else 0.0,
            "std_discount_pct": pstdev(discounts) if len(discounts) > 1 else 0.0,
            "p95_discount_pct": self._percentile(discounts, 0.95),
            "avg_price_override_pct": mean(overrides) if overrides else 0.0,
            "std_price_override_pct": pstdev(overrides) if len(overrides) > 1 else 0.0,
            "avg_deleted_lines": mean(deleted) if deleted else 0.0,
            "p95_deleted_lines": self._percentile(deleted, 0.95),
            "avg_refund_amount": mean(refunds) if refunds else 0.0,
            "p95_refund_amount": self._percentile(refunds, 0.95),
            "refund_frequency": (
                sum(1 for value in values if value["refund_amount"] > 0) / len(values)
                if values else 0.0
            ),
        }

    @api.model
    def _upsert_baseline(self, company, level, cashier, config, start, end, orders):
        if not orders:
            return self.browse()
        if level == "cashier":
            subject_key = "cashier:%s|config:%s" % (cashier.id, config.id)
        elif level == "pos":
            subject_key = "pos:%s" % config.id
        else:
            subject_key = "company:%s" % company.id
        values = {
            "subject_key": subject_key,
            "cashier_id": cashier.id if cashier else False,
            "config_id": config.id if config else False,
            "company_id": company.id,
            "baseline_level": level,
            "period_start": start,
            "period_end": end,
            "calculated_at": fields.Datetime.now(),
        }
        values.update(self._statistics(orders))
        baseline = self.search([
            ("company_id", "=", company.id),
            ("subject_key", "=", subject_key),
            ("period_start", "=", start),
            ("period_end", "=", end),
        ], limit=1)
        if baseline:
            baseline.write(values)
        else:
            baseline = self.create(values)
        return baseline

    @api.model
    def recalculate_for_company(self, company=None, end=None):
        company = company or self.env.company
        end = end or fields.Datetime.now()
        start = end - timedelta(days=company.pos_risk_baseline_lookback_days)
        Order = self.env["pos.order"].sudo()
        base_domain = [
            ("company_id", "=", company.id),
            ("state", "in", ("paid", "done")),
            ("date_order", ">=", start),
            ("date_order", "<", end),
            ("config_id.pos_risk_monitoring_enabled", "=", True),
        ]
        orders = Order.search(base_domain)
        created = self.browse()
        configs = orders.mapped("config_id")
        for config in configs:
            config_orders = orders.filtered(lambda order: order.config_id == config)
            created |= self._upsert_baseline(
                company, "pos", False, config, start, end, config_orders
            )
            cashiers = config_orders.mapped("user_id")
            for cashier in cashiers:
                cashier_orders = config_orders.filtered(lambda order: order.user_id == cashier)
                created |= self._upsert_baseline(
                    company, "cashier", cashier, config, start, end, cashier_orders
                )
        created |= self._upsert_baseline(
            company, "company", False, False, start, end, orders
        )
        return created

    @api.model
    def _cron_recalculate_baselines(self):
        for company in self.env["res.company"].search([]):
            self.recalculate_for_company(company)
        return True

    @api.model
    def select_for_order(self, order):
        company = order.company_id
        minimum = company.pos_risk_baseline_min_sample
        end = fields.Datetime.now()
        start = end - timedelta(days=company.pos_risk_baseline_lookback_days)
        candidates = [
            ("cashier", "cashier:%s|config:%s" % (order.user_id.id, order.config_id.id)),
            ("pos", "pos:%s" % order.config_id.id),
            ("company", "company:%s" % company.id),
        ]
        for level, subject_key in candidates:
            baseline = self.search([
                ("company_id", "=", company.id),
                ("subject_key", "=", subject_key),
                ("period_start", ">=", start),
                ("period_end", "<=", end),
            ], limit=1, order="period_end desc, id desc")
            if baseline and (level != "cashier" or baseline.sample_count >= minimum):
                return baseline
        return self.browse()
