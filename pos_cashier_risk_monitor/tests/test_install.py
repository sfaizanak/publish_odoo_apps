# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskMonitorInstall(TransactionCase):
    """Phase 1 smoke test.

    Only verifies that the addon installed cleanly and that its security
    groups and the single Phase-1 field exist and behave as expected.
    Detection logic, rules, events and cases do not exist yet and are
    intentionally out of scope here.
    """

    def test_module_installed(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "pos_cashier_risk_monitor")]
        )
        self.assertTrue(module, "Module record not found.")
        self.assertEqual(module.state, "installed")

    def test_security_groups_exist_and_are_chained(self):
        user_group = self.env.ref(
            "pos_cashier_risk_monitor.group_pos_risk_user"
        )
        manager_group = self.env.ref(
            "pos_cashier_risk_monitor.group_pos_risk_manager"
        )
        admin_group = self.env.ref(
            "pos_cashier_risk_monitor.group_pos_risk_admin"
        )

        self.assertIn(user_group, manager_group.implied_ids)
        self.assertIn(manager_group, admin_group.implied_ids)

    def test_pos_config_risk_flag_defaults_false(self):
        pos_config = self.env["pos.config"].create(
            {"name": "Test POS - Risk Monitor Phase 1"}
        )
        self.assertFalse(pos_config.pos_risk_monitoring_enabled)

        pos_config.pos_risk_monitoring_enabled = True
        self.assertTrue(pos_config.pos_risk_monitoring_enabled)
