# -*- coding: utf-8 -*-
import base64
import pickle
from datetime import timedelta
from statistics import mean, pstdev

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


FEATURE_NAMES = (
    "max_discount_pct",
    "discount_amount_ratio",
    "max_price_deviation_pct",
    "manual_override_count",
    "deleted_line_count",
    "deleted_line_value_ratio",
    "refund_amount_ratio",
    "refund_line_count",
    "unlinked_refund_line_count",
    "order_total",
    "line_count",
    "hour_sin",
    "hour_cos",
    "cashier_recent_refund_count",
    "cashier_recent_high_discount_count",
)


class PosRiskMlModel(models.Model):
    _name = "pos.risk.ml.model"
    _description = "POS Risk Isolation Forest Model"
    _order = "trained_at desc, id desc"

    _company_config_unique = models.Constraint(
        "unique(company_id, config_id)",
        "Only one current ML model is allowed per company and POS.",
    )

    name = fields.Char(required=True, readonly=True, default=lambda self: _("New"))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, index=True,
                                 default=lambda self: self.env.company)
    config_id = fields.Many2one("pos.config", required=True, index=True)
    state = fields.Selection([
        ("draft", "Draft"), ("trained", "Trained"), ("error", "Error"),
    ], required=True, default="draft", index=True)
    version = fields.Char(required=True, default="isolation-forest-v1")
    feature_schema = fields.Json(default=lambda self: list(FEATURE_NAMES))
    period_start = fields.Datetime()
    period_end = fields.Datetime()
    sample_count = fields.Integer(default=0)
    parameters = fields.Json()
    model_blob = fields.Binary(attachment=False)
    trained_at = fields.Datetime()
    error_message = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = _("Isolation Forest - %s") % (
                    self.env["pos.config"].browse(vals.get("config_id")).display_name
                    if vals.get("config_id") else _("POS")
                )
            vals.setdefault("feature_schema", list(FEATURE_NAMES))
        return super().create(vals_list)

    @api.constrains("config_id", "company_id")
    def _check_company_config(self):
        for model in self:
            if model.config_id.company_id != model.company_id:
                raise ValidationError(_("The ML model POS must belong to its company."))

    @staticmethod
    def feature_vector(features):
        total = max(abs(float(features.get("order_total", 0.0))), 1.0)
        hour = float(features.get("hour_of_day", 0.0)) / 24.0 * 6.283185307
        return [
            float(features.get("max_discount_pct", 0.0)),
            float(features.get("discount_amount", 0.0)) / total,
            float(features.get("max_price_deviation_pct", 0.0)),
            float(features.get("manual_override_count", 0.0)),
            float(features.get("deleted_line_count", 0.0)),
            float(features.get("deleted_line_value", 0.0)) / total,
            float(features.get("refund_amount", 0.0)) / total,
            float(features.get("refund_line_count", 0.0)),
            float(features.get("unlinked_refund_line_count", 0.0)),
            total,
            float(features.get("line_count", 0.0)),
            __import__("math").sin(hour),
            __import__("math").cos(hour),
            float(features.get("cashier_recent_refund_count", 0.0)),
            float(features.get("cashier_recent_high_discount_count", 0.0)),
        ]

    @api.model
    def _isolation_forest_class(self):
        try:
            from sklearn.ensemble import IsolationForest
            return IsolationForest
        except ImportError:
            return None

    def _require_admin(self):
        if not self.env.user.has_group("pos_cashier_risk_monitor.group_pos_risk_admin"):
            raise AccessError(_("Only risk administrators can train ML models."))

    @api.model
    def train_for_config(self, config, end=None):
        company = config.company_id
        end = end or fields.Datetime.now()
        start = end - timedelta(days=company.pos_risk_ml_lookback_days)
        Model = self.sudo()
        model = Model.search([
            ("company_id", "=", company.id), ("config_id", "=", config.id),
        ], limit=1) or Model.create({
            "company_id": company.id, "config_id": config.id,
        })
        orders = self.env["pos.order"].sudo().search([
            ("company_id", "=", company.id),
            ("config_id", "=", config.id),
            ("state", "in", ("paid", "done")),
            ("date_order", ">=", start),
            ("date_order", "<", end),
        ])
        Forest = model._isolation_forest_class()
        if Forest is None:
            model.write({"state": "error", "error_message": _(
                "Scikit-learn is not installed; deterministic analysis remains active."
            )})
            return model
        minimum = max(company.pos_risk_baseline_min_sample, 10)
        if len(orders) < minimum:
            model.write({"state": "error", "sample_count": len(orders), "error_message": _(
                "At least %(minimum)s completed orders are required; found %(count)s."
            ) % {"minimum": minimum, "count": len(orders)}})
            return model
        vectors = [model.feature_vector(order._risk_extract_features()) for order in orders]
        estimator = Forest(
            n_estimators=100,
            contamination="auto",
            random_state=42,
        )
        estimator.fit(vectors)
        feature_means = [mean(column) for column in zip(*vectors)]
        feature_stds = [pstdev(column) if len(column) > 1 else 0.0 for column in zip(*vectors)]
        model.write({
            "state": "trained",
            "version": "isolation-forest-v1-%s" % fields.Datetime.now().strftime("%Y%m%d%H%M%S"),
            "feature_schema": list(FEATURE_NAMES),
            "period_start": start,
            "period_end": end,
            "sample_count": len(vectors),
            "parameters": {
                "n_estimators": 100,
                "contamination": "auto",
                "random_state": 42,
                "feature_means": feature_means,
                "feature_stds": feature_stds,
            },
            "model_blob": base64.b64encode(pickle.dumps(estimator)),
            "trained_at": fields.Datetime.now(),
            "error_message": False,
        })
        return model

    def action_train(self):
        self._require_admin()
        for model in self:
            model.train_for_config(model.config_id)
        return True

    @api.model
    def _cron_train_models(self):
        for config in self.env["pos.config"].search([
            ("pos_risk_monitoring_enabled", "=", True),
            ("company_id.pos_risk_ml_enabled", "=", True),
        ]):
            self.train_for_config(config)
        return True

    def score_features(self, features):
        self.ensure_one()
        if self.state != "trained" or not self.model_blob:
            return 0.0, []
        try:
            estimator = pickle.loads(base64.b64decode(self.model_blob))
            vector = self.feature_vector(features)
            decision = float(estimator.decision_function([vector])[0])
            score = max(0.0, min(100.0, (0.5 - decision) * 100.0))
            means = (self.parameters or {}).get("feature_means", [])
            stds = (self.parameters or {}).get("feature_stds", [])
            deviations = []
            for index, observed in enumerate(vector):
                if index >= len(means):
                    continue
                deviation = ((observed - means[index]) / stds[index]) if stds[index] else 0.0
                if deviation > 0:
                    deviations.append((FEATURE_NAMES[index], observed, means[index], deviation))
            deviations.sort(key=lambda item: item[3], reverse=True)
            return score, deviations[:3]
        except Exception:
            return 0.0, []
