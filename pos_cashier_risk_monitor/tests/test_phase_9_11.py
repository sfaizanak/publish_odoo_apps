# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskPhasesNineToEleven(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({
            "name": "Risk Phase 9-11 POS",
            "pos_risk_monitoring_enabled": True,
        })
        cls.session = cls.env["pos.session"].create({
            "name": "Risk Phase 9-11 Session",
            "config_id": cls.config.id,
            "user_id": cls.env.uid,
            "state": "opened",
        })
        cls.order = cls.env["pos.order"].create({
            "name": "RISK-PHASE-9-11",
            "state": "paid",
            "amount_tax": 0,
            "amount_total": 100,
            "amount_paid": 100,
            "amount_return": 0,
            "company_id": cls.env.company.id,
            "config_id": cls.config.id,
            "session_id": cls.session.id,
        })

    def test_baseline_falls_back_to_pos_when_cashier_sample_is_small(self):
        now = fields.Datetime.now()
        start = now - timedelta(days=30)
        baseline_model = self.env["pos.cashier.baseline"]
        baseline_model.create({
            "subject_key": "pos:%s" % self.config.id,
            "config_id": self.config.id,
            "company_id": self.env.company.id,
            "baseline_level": "pos",
            "period_start": start,
            "period_end": now,
            "sample_count": 40,
            "avg_discount_pct": 4,
            "std_discount_pct": 1,
            "p95_discount_pct": 6,
        })
        cashier = self.env["res.users"].browse(self.order.user_id.id)
        baseline_model.create({
            "subject_key": "cashier:%s|config:%s" % (cashier.id, self.config.id),
            "cashier_id": cashier.id,
            "config_id": self.config.id,
            "company_id": self.env.company.id,
            "baseline_level": "cashier",
            "period_start": start,
            "period_end": now,
            "sample_count": 2,
        })

        selected = baseline_model.select_for_order(self.order)

        self.assertEqual(selected.baseline_level, "pos")
        self.assertEqual(selected.sample_count, 40)

    def test_hybrid_scoring_uses_baseline_without_crashing(self):
        now = fields.Datetime.now()
        self.env["pos.cashier.baseline"].create({
            "subject_key": "pos:%s" % self.config.id,
            "config_id": self.config.id,
            "company_id": self.env.company.id,
            "baseline_level": "pos",
            "period_start": now - timedelta(days=30),
            "period_end": now,
            "sample_count": 40,
            "avg_discount_pct": 4,
            "std_discount_pct": 1,
            "p95_discount_pct": 6,
        })

        features = self.order._risk_extract_features()
        score = self.order._risk_anomaly_score(features)

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertTrue(features["_baseline_available"])

    def test_high_risk_activity_is_idempotent(self):
        manager = self.env["res.users"].create({
            "name": "Phase 9 Risk Manager",
            "login": "phase-9-risk-manager",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("pos_cashier_risk_monitor.group_pos_risk_manager").id,
            ])],
        })
        self.env.company.write({"pos_risk_manager_ids": [(6, 0, [manager.id])]})
        case = self.env["pos.risk.case"].create({
            "order_id": self.order.id,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
            "category": "discount",
            "classification": "requires_review",
            "risk_level": "high",
            "risk_score": 75,
            "fingerprint": "phase-9-notification",
        })

        case._risk_notify_stakeholders()
        case._risk_notify_stakeholders()

        model_id = self.env["ir.model"]._get_id("pos.risk.case")
        activities = self.env["mail.activity"].search([
            ("res_model_id", "=", model_id),
            ("res_id", "=", case.id),
            ("user_id", "=", manager.id),
        ])
        self.assertEqual(len(activities), 1)
