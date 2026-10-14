# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskPhasesTwelveThirteen(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({
            "name": "Risk Reporting ML POS",
            "pos_risk_monitoring_enabled": True,
        })

    def test_ml_feature_vector_has_stable_schema(self):
        model = self.env["pos.risk.ml.model"]
        vector = model.feature_vector({
            "max_discount_pct": 25,
            "discount_amount": 10,
            "order_total": 100,
            "max_price_deviation_pct": 30,
            "manual_override_count": 1,
            "deleted_line_count": 2,
            "deleted_line_value": 50,
            "refund_amount": 0,
            "refund_line_count": 0,
            "unlinked_refund_line_count": 0,
            "line_count": 3,
            "hour_of_day": 14,
        })

        self.assertEqual(len(vector), 15)
        self.assertEqual(len(model.feature_vector({})), len(vector))

    def test_ml_training_falls_back_when_sample_is_insufficient(self):
        model = self.env["pos.risk.ml.model"].train_for_config(self.config)

        self.assertEqual(model.state, "error")
        self.assertIn("completed orders", model.error_message)
        self.assertEqual(model.score_features({"order_total": 100})[0], 0.0)
