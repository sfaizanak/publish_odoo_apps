# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskRuleMaster(TransactionCase):

    def test_seed_rules_are_available_and_read_only_to_manager(self):
        rule = self.env.ref("pos_cashier_risk_monitor.rule_high_discount")
        self.assertEqual(rule.code, "HIGH_DISCOUNT")
        self.assertEqual(rule.category, "discount")
        self.assertEqual(rule.threshold_value, 25.0)

    def test_initial_catalogue_covers_phase_seven_categories(self):
        codes = set(self.env["pos.risk.rule"].search([]).mapped("code"))
        self.assertTrue({
            "HIGH_DISCOUNT",
            "NEGATIVE_MARGIN",
            "DRASTIC_PRICE_DECREASE",
            "DRASTIC_PRICE_INCREASE",
            "EXCESSIVE_LINE_DELETION",
            "HIGH_VALUE_LINE_DELETION",
            "UNLINKED_REFUND",
            "HIGH_VALUE_REFUND",
            "REPEATED_REFUNDS",
            "COMBINED_OVERRIDE_DELETE",
        } <= codes)

    def test_company_score_weights_must_be_non_negative_and_sum_to_one(self):
        company = self.env.company
        with self.assertRaises(ValidationError):
            company.write({"pos_risk_rule_score_weight": -0.1})
        with self.assertRaises(ValidationError):
            company.write({"pos_risk_rule_score_weight": 0.8})
