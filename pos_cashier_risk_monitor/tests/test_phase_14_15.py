# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestPosRiskEvaluation(TransactionCase):
    def test_demo_scenario_catalogue_contains_ten_scenarios(self):
        run = self.env.ref(
            "pos_cashier_risk_monitor.demo_evaluation_run", raise_if_not_found=False
        )
        if not run:
            self.skipTest("Demo data is disabled for this database")
        self.assertEqual(len(run.scenario_ids), 10)
        self.assertEqual(len(run.scenario_ids.mapped("code")), 10)

    def test_unlinked_scenario_is_not_marked_as_evaluated(self):
        scenario = self.env["pos.risk.evaluation.scenario"].create({
            "name": "Unlinked test scenario",
            "code": "UNLINKED_TEST",
            "description": "A scenario without a POS order.",
            "category": "normal",
            "expected_alert": False,
            "expected_outcome": "no_alert",
            "expected_level": "none",
        })
        scenario.action_evaluate()
        self.assertFalse(scenario.evaluated)
        self.assertIn("No POS order", scenario.evaluation_notes)

    def test_evaluation_metrics_are_safe_when_empty(self):
        run = self.env["pos.risk.evaluation"].create({"name": "Empty test run"})
        self.assertEqual(run.precision, 0.0)
        self.assertEqual(run.false_alerts_per_1000, 0.0)
        self.assertEqual(run.acceptance_rate, 0.0)
