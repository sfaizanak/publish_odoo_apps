# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskAnalysisJob(TransactionCase):

    def test_unlinked_refund_is_exposed_as_a_feature(self):
        config = self.env["pos.config"].create({"name": "Refund Feature POS"})
        session = self.env["pos.session"].create({
            "name": "Refund Feature Session",
            "config_id": config.id,
            "user_id": self.env.uid,
            "state": "opened",
        })
        order = self.env["pos.order"].create({
            "name": "RISK-REFUND-ORDER",
            "state": "paid",
            "is_refund": True,
            "amount_tax": 0,
            "amount_total": -10,
            "amount_paid": -10,
            "amount_return": 0,
            "company_id": self.env.company.id,
            "config_id": config.id,
            "session_id": session.id,
        })

        features = order._risk_extract_features()

        self.assertEqual(features["unlinked_refund_line_count"], 0)
        self.assertEqual(features["refund_amount"], 10)

    def test_pending_order_is_processed_by_bounded_cron(self):
        config = self.env["pos.config"].create({
            "name": "Risk Analysis Cron POS",
            "pos_risk_monitoring_enabled": True,
        })
        session = self.env["pos.session"].create({
            "name": "Risk Analysis Cron Session",
            "config_id": config.id,
            "user_id": self.env.uid,
            "state": "opened",
        })
        order = self.env["pos.order"].create({
            "name": "RISK-CRON-ORDER",
            "state": "paid",
            "amount_tax": 0,
            "amount_total": 0,
            "amount_paid": 0,
            "amount_return": 0,
            "company_id": self.env.company.id,
            "config_id": config.id,
            "session_id": session.id,
            "risk_analysis_state": "pending",
        })

        self.env["pos.order"]._cron_process_pending_risk_orders(limit=1)

        self.assertEqual(order.risk_analysis_state, "completed")
        self.assertEqual(order.risk_level, "none")
        self.assertTrue(order.risk_analyzed_at)
