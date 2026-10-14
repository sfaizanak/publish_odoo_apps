# -*- coding: utf-8 -*-
"""Explainable POS risk feature extraction, rules and scoring."""

from collections import defaultdict

from odoo import _, api, fields, models


OPERATOR_FUNCTIONS = {
    "gte": lambda actual, expected: actual >= expected,
    "gt": lambda actual, expected: actual > expected,
    "lte": lambda actual, expected: actual <= expected,
    "lt": lambda actual, expected: actual < expected,
    "eq": lambda actual, expected: actual == expected,
    "neq": lambda actual, expected: actual != expected,
}


class PosOrderRiskEngine(models.Model):
    _inherit = "pos.order"

    @api.model
    def _risk_compare(self, actual, operator, expected):
        """Compare values using only the whitelisted rule operators."""
        return OPERATOR_FUNCTIONS.get(operator, lambda *_args: False)(
            actual, expected
        )

    def _risk_extract_features(self):
        """Return normalized, explainable features for one POS order."""
        self.ensure_one()
        lines = self.lines
        events = self.env["pos.risk.event"].sudo().search([("order_id", "=", self.id)])
        event_counts = defaultdict(int)
        deleted_line_value = 0.0
        for event in events:
            event_counts[event.event_type] += 1
            if event.event_type == "line_deleted":
                deleted_line_value += abs(
                    float(event.new_numeric_value or event.old_numeric_value or 0.0)
                )

        line_features = []
        for line in lines:
            discount = float(line.discount or 0.0)
            final_unit_price = line.price_unit * (1.0 - discount / 100.0)
            cost = float(line.product_id.standard_price or 0.0)
            margin = final_unit_price - cost
            override_difference = float(line.risk_price_override_difference or 0.0)
            override_percentage = float(line.risk_price_override_percentage or 0.0)
            reference_unit_price = float(
                line.risk_original_unit_price or line.price_unit or 0.0
            )
            discount_exposure = max(reference_unit_price - final_unit_price, 0.0) * abs(
                float(line.qty or 0.0)
            )
            override_exposure = max(
                reference_unit_price - float(line.price_unit or 0.0), 0.0
            ) * abs(float(line.qty or 0.0))
            line_features.append({
                "line": line,
                "discount_percentage": discount,
                "final_unit_price": final_unit_price,
                "reference_unit_price": reference_unit_price,
                "quantity": float(line.qty or 0.0),
                "margin": margin,
                "price_override_percentage": override_percentage,
                "price_override_decrease_percentage": (
                    override_percentage if override_difference < 0 else 0.0
                ),
                "price_override_increase_percentage": (
                    override_percentage if override_difference > 0 else 0.0
                ),
                "discount_exposure": discount_exposure,
                "override_exposure": override_exposure,
                "financial_exposure": max(discount_exposure, override_exposure),
            })

        return {
            "order": self,
            "order_id": self.id,
            "company_id": self.company_id.id,
            "config_id": self.config_id.id,
            "session_id": self.session_id.id,
            "cashier_id": self.user_id.id,
            "order_datetime": self.date_order,
            "line_features": line_features,
            "events": events,
            "order_total": abs(float(self.amount_total or 0.0)),
            "absolute_order_total": abs(float(self.amount_total or 0.0)),
            "line_count": len(lines),
            "discounted_line_count": sum(
                1 for line in line_features if line["discount_percentage"] > 0
            ),
            "max_discount_pct": max(
                (line["discount_percentage"] for line in line_features), default=0.0
            ),
            "average_discount_pct": (
                sum(line["discount_percentage"] for line in line_features) / len(line_features)
                if line_features else 0.0
            ),
            "discount_amount": sum(line["discount_exposure"] for line in line_features),
            "manual_override_count": sum(
                1 for line in lines if line.risk_is_manual_price_override
            ),
            "max_price_deviation_pct": max(
                (line["price_override_percentage"] for line in line_features), default=0.0
            ),
            "price_override_exposure": sum(
                line["override_exposure"] for line in line_features
            ),
            "refund_amount": abs(float(self.amount_total or 0.0)) if self.is_refund else 0.0,
            "refund_line_count": len(lines) if self.is_refund else 0,
            "unlinked_refund_line_count": (
                len(lines) if self.is_refund and not self.refunded_order_id else 0
            ),
            "customer_id": self.partner_id.id if self.partner_id else False,
            "hour_of_day": float(fields.Datetime.context_timestamp(
                self, self.date_order or fields.Datetime.now()
            ).hour),
            "cashier_recent_refund_count": 0,
            "cashier_recent_high_discount_count": 0,
            "deleted_line_count": event_counts["line_deleted"],
            "deleted_line_value": deleted_line_value,
            "event_counts": dict(event_counts),
            "event_count": len(events),
            "cancelled": self.state == "cancel" or bool(event_counts["order_cancelled"]),
            "financial_exposure": abs(float(self.amount_total or 0.0)),
        }

    @api.model
    def _risk_rule_feature(self, rule, features, line_feature=None):
        """Map a configured rule to one normalized feature value."""
        code = (rule.code or "").upper()
        if code == "NEGATIVE_MARGIN":
            return (line_feature or {}).get("margin", 0.0)
        if code == "HIGH_VALUE_LINE_DELETION":
            return features.get("deleted_line_value", 0.0)
        if code == "REPEATED_REFUNDS":
            cutoff = fields.Datetime.subtract(
                fields.Datetime.now(), minutes=rule.window_minutes
            ) if rule.window_minutes else False
            return sum(
                1 for event in features["events"]
                if event.event_type == "refund_started"
                and (not cutoff or event.event_at >= cutoff)
            )
        if code == "COMBINED_OVERRIDE_DELETE":
            return features["manual_override_count"] + features["deleted_line_count"]
        if code == "UNLINKED_REFUND":
            return features.get("unlinked_refund_line_count", 0)
        if rule.category == "discount":
            return (line_feature or {}).get("discount_percentage", 0.0)
        if rule.category == "price_override":
            if "DECREASE" in (rule.code or "").upper():
                return (line_feature or {}).get("price_override_decrease_percentage", 0.0)
            if "INCREASE" in (rule.code or "").upper():
                return (line_feature or {}).get("price_override_increase_percentage", 0.0)
            return (line_feature or {}).get("price_override_percentage", 0.0)
        if rule.category == "deletion":
            return features["deleted_line_count"]
        if rule.category == "cancellation":
            return 1.0 if features["cancelled"] else 0.0
        if rule.category == "refund":
            return features["refund_amount"]
        if rule.category == "timing":
            return float(fields.Datetime.context_timestamp(
                self, self.date_order or fields.Datetime.now()
            ).hour)
        return float(features["event_count"])

    @api.model
    def _risk_rule_applies(self, rule, features, line_feature=None):
        actual = self._risk_rule_feature(rule, features, line_feature)
        amount = (line_feature or {}).get("financial_exposure", features["financial_exposure"])
        if rule.minimum_amount and amount < rule.minimum_amount:
            return False, actual
        return self._risk_compare(actual, rule.operator, rule.threshold_value), actual

    def _risk_evaluate_rules(self, features):
        """Return triggered rules with their observed values and exposure."""
        self.ensure_one()
        # POS cashiers can trigger automatic analysis through order sync, but
        # rule configuration remains restricted to monitoring users/managers.
        Rule = self.env["pos.risk.rule"].sudo()
        rules = Rule.search([
            "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            "|", ("config_ids", "=", False), ("config_ids", "in", self.config_id.id),
        ])
        results = []
        for rule in rules:
            candidates = features["line_features"] if rule.scope == "line" else [None]
            for line_feature in candidates:
                matched, actual = self._risk_rule_applies(rule, features, line_feature)
                if not matched:
                    continue
                exposure = (line_feature or {}).get(
                    "financial_exposure", features["financial_exposure"]
                )
                results.append({
                    "rule": rule,
                    "line": (line_feature or {}).get("line"),
                    "actual": actual,
                    "exposure": exposure,
                })
        return results

    def _risk_score_results(self, results, features):
        company = self.company_id
        weighted_total = sum(
            result["rule"].severity_score * result["rule"].risk_weight
            for result in results
        )
        weight_total = sum(result["rule"].risk_weight for result in results)
        rule_score = min(100.0, weighted_total / weight_total) if weight_total else 0.0
        exposure = sum(result["exposure"] for result in results)
        order_total = max(features["order_total"], 1.0)
        impact_score = min(100.0, exposure / order_total * 100.0)
        anomaly_score = self._risk_anomaly_score(features)
        if features.get("_baseline_available"):
            weights = (
                company.pos_risk_rule_score_weight,
                company.pos_risk_anomaly_score_weight,
                company.pos_risk_impact_score_weight,
            )
            components = (rule_score, anomaly_score, impact_score)
        else:
            # Do not silently reduce alerts while there is no historical
            # baseline. Redistribute the available rule and impact weights.
            weights = (
                company.pos_risk_rule_score_weight,
                company.pos_risk_impact_score_weight,
            )
            components = (rule_score, impact_score)
        weight_total = sum(weights) or 1.0
        risk_score = min(100.0, sum(
            component * weight / weight_total
            for component, weight in zip(components, weights)
        ))
        if risk_score >= company.pos_risk_critical_threshold:
            risk_level = "critical"
        elif risk_score >= company.pos_risk_high_threshold:
            risk_level = "high"
        elif risk_score >= company.pos_risk_case_creation_threshold:
            risk_level = "medium"
        else:
            risk_level = "low"
        return rule_score, anomaly_score, impact_score, risk_score, risk_level, exposure

    def _risk_anomaly_score(self, features):
        """Compare this order with its best available historical baseline."""
        baseline = self.env["pos.cashier.baseline"].sudo().select_for_order(self)
        features["_baseline_available"] = bool(baseline)
        features["_baseline"] = baseline
        if not baseline:
            features["_baseline_reason"] = _(
                "No baseline with sufficient historical data was available."
            )
            baseline_score = 0.0
            features["_baseline_deviations"] = []
        else:
            comparisons = [
                ("discount", features["average_discount_pct"], baseline.avg_discount_pct,
                 baseline.std_discount_pct, baseline.p95_discount_pct),
                ("price override", features["max_price_deviation_pct"], baseline.avg_price_override_pct,
                 baseline.std_price_override_pct, baseline.avg_price_override_pct),
                ("deleted lines", features["deleted_line_count"], baseline.avg_deleted_lines,
                 0.0, baseline.p95_deleted_lines),
                ("refund amount", features["refund_amount"], baseline.avg_refund_amount,
                 0.0, baseline.p95_refund_amount),
            ]
            deviations = []
            for label, observed, average, std, p95 in comparisons:
                if std:
                    z_score = (observed - average) / std
                elif observed > max(average, p95):
                    z_score = 3.0
                else:
                    z_score = 0.0
                if z_score > 0:
                    deviations.append((label, observed, average, z_score))
            deviations.sort(key=lambda item: item[3], reverse=True)
            features["_baseline_deviations"] = deviations
            features["_baseline_reason"] = _(
                "Selected %(level)s baseline with %(sample)s completed orders."
            ) % {"level": baseline.baseline_level, "sample": baseline.sample_count}
            baseline_score = min(
                100.0,
                max((deviation[3] for deviation in deviations), default=0.0) / 3.0 * 100.0,
            )
        ml_score = 0.0
        features["_ml_model_version"] = False
        if self.company_id.pos_risk_ml_enabled:
            ml_model = self.env["pos.risk.ml.model"].sudo().search([
                ("company_id", "=", self.company_id.id),
                ("config_id", "=", self.config_id.id),
                ("state", "=", "trained"),
            ], limit=1)
            if ml_model:
                ml_score, _ml_deviations = ml_model.score_features(features)
                features["_ml_model_version"] = ml_model.version
                features["_ml_deviations"] = _ml_deviations
        features["_baseline_score"] = baseline_score
        features["_ml_score"] = ml_score
        return max(baseline_score, ml_score)

    def _risk_create_or_update_case(self, results, scores):
        self.ensure_one()
        rule_score, anomaly_score, impact_score, risk_score, risk_level, exposure = scores
        if risk_score < self.company_id.pos_risk_case_creation_threshold:
            return self.env["pos.risk.case"]

        Case = self.env["pos.risk.case"].sudo()
        Reason = self.env["pos.risk.case.reason"].sudo()
        cases = self.env["pos.risk.case"]
        grouped_results = defaultdict(list)
        for result in results:
            grouped_results[result["rule"].category].append(result)
        for category, category_results in grouped_results.items():
            first = category_results[0]
            classification = next(
                (result["rule"].case_classification for result in category_results
                 if result["rule"].case_classification),
                "requires_review",
            )
            category_exposure = sum(result["exposure"] for result in category_results)
            explanation = _("%s rule(s) triggered in the %s category during POS risk analysis.") % (
                len(category_results), category
            )
            baseline = self.env.context.get("risk_features", {}).get("_baseline_reason")
            if baseline:
                explanation += " " + baseline
            ml_version = self.env.context.get("risk_features", {}).get("_ml_model_version")
            if ml_version:
                explanation += " " + _("Isolation Forest model %(version)s was available.") % {
                    "version": ml_version,
                }
            recommended_action = "\n".join(
                dict.fromkeys(result["rule"].recommended_action for result in category_results
                              if result["rule"].recommended_action)
            )
            fingerprint = "company:%s|order:%s|category:%s|model:rules-v1" % (
                self.company_id.id, self.id, category
            )
            values = {
                "fingerprint": fingerprint,
                "company_id": self.company_id.id,
                "order_id": self.id,
                "order_line_id": first["line"].id if first["line"] else False,
                "cashier_id": self.user_id.id,
                "session_id": self.session_id.id,
                "config_id": self.config_id.id,
                "category": category,
                "classification": classification,
                "rule_score": rule_score,
                "anomaly_score": anomaly_score,
                "impact_score": impact_score,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "currency_id": self.currency_id.id,
                "financial_exposure": category_exposure,
                "explanation": explanation,
                "recommended_action": recommended_action,
                "model_version": "rules+baseline-v1%s" % (
                    "|ml:%s" % self.env.context.get("risk_features", {}).get("_ml_model_version")
                    if self.env.context.get("risk_features", {}).get("_ml_model_version")
                    else "",
                ),
            }
            case = Case.search([("fingerprint", "=", fingerprint)], limit=1)
            case = case or Case.create(values)
            case.write(values)
            case.reason_ids.unlink()
            Reason.create([{
                "case_id": case.id,
                "rule_id": result["rule"].id,
                "reason_code": result["rule"].code,
                "description": result["rule"].description or result["rule"].name,
                "observed_value": result["actual"],
                "expected_value": result["rule"].threshold_value,
                "deviation_value": result["actual"] - result["rule"].threshold_value,
                "contribution_score": min(100.0, result["rule"].severity_score),
                "financial_exposure": result["exposure"],
            } for result in category_results])
            features = self.env.context.get("risk_features", {})
            for sequence, deviation in enumerate(features.get("_baseline_deviations", []), 100):
                Reason.create({
                    "case_id": case.id,
                    "reason_code": "BASELINE_%s" % deviation[0].upper().replace(" ", "_"),
                    "description": _(
                        "Observed %(observed)s for %(metric)s versus baseline average %(average)s."
                    ) % {
                        "observed": deviation[1],
                        "metric": deviation[0],
                        "average": deviation[2],
                    },
                    "observed_value": deviation[1],
                    "expected_value": deviation[2],
                    "deviation_value": deviation[1] - deviation[2],
                    "contribution_score": min(100.0, deviation[3] / 3.0 * 100.0),
                    "sequence": sequence,
                })
            for sequence, deviation in enumerate(features.get("_ml_deviations", []), 200):
                Reason.create({
                    "case_id": case.id,
                    "reason_code": "ML_%s" % deviation[0].upper(),
                    "description": _(
                        "Isolation Forest feature %(metric)s was %(observed)s versus training average %(average)s."
                    ) % {
                        "metric": deviation[0],
                        "observed": deviation[1],
                        "average": deviation[2],
                    },
                    "observed_value": deviation[1],
                    "expected_value": deviation[2],
                    "deviation_value": deviation[1] - deviation[2],
                    "contribution_score": min(100.0, deviation[3] / 3.0 * 100.0),
                    "sequence": sequence,
                })
            cases |= case
        return cases

    @api.model
    def _cron_process_pending_risk_orders(self, limit=100):
        """Analyze completed monitored orders in bounded, retryable batches."""
        orders = self.search([
            ("risk_analysis_state", "=", "pending"),
            ("state", "in", ("paid", "done")),
            ("config_id.pos_risk_monitoring_enabled", "=", True),
        ], limit=limit, order="id")
        for order in orders:
            order._risk_run_analysis()
        return True

    def _risk_run_analysis(self):
        for order in self:
            if not order._risk_monitoring_enabled():
                order.with_context(skip_risk_state_mark=True).write({
                    "risk_analysis_state": "not_required",
                    "risk_score": 0.0,
                    "risk_level": "none",
                })
                continue
            order.with_context(skip_risk_state_mark=True).write({
                "risk_analysis_state": "processing",
                "risk_analysis_error": False,
            })
            try:
                features = order._risk_extract_features()
                results = order._risk_evaluate_rules(features)
                scores = order._risk_score_results(results, features)
                case = order.with_context(risk_features=features)._risk_create_or_update_case(scores=scores, results=results) if results else self.env["pos.risk.case"]
                order.with_context(skip_risk_state_mark=True).write({
                    "risk_analysis_state": "completed",
                    "risk_score": scores[3],
                    "risk_level": scores[4] if results else "none",
                    "risk_analyzed_at": fields.Datetime.now(),
                    "risk_analysis_error": False,
                })
                for risk_case in case:
                    risk_case.message_post(body=_("Automatically analyzed from POS order events."))
                    risk_case._risk_notify_stakeholders()
            except Exception as error:
                order.with_context(skip_risk_state_mark=True).write({
                    "risk_analysis_state": "failed",
                    "risk_analysis_error": str(error),
                })
        return True
