# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosRiskCaseWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env["pos.config"].create({"name": "Risk Workflow POS"})
        cls.session = cls.env["pos.session"].create({
            "name": "Risk Workflow Session",
            "config_id": cls.config.id,
            "user_id": cls.env.uid,
            "state": "opened",
        })
        cls.order = cls.env["pos.order"].create({
            "name": "RISK-TEST-ORDER",
            "amount_tax": 0,
            "amount_total": 0,
            "amount_paid": 0,
            "amount_return": 0,
            "company_id": cls.env.company.id,
            "session_id": cls.session.id,
        })
        cls.manager = cls.env["res.users"].create({
            "name": "Risk Test Manager",
            "login": "risk-test-manager",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("pos_cashier_risk_monitor.group_pos_risk_manager").id,
            ])],
        })

    def _case(self, **values):
        vals = {
            "fingerprint": values.pop("fingerprint", "workflow-fingerprint"),
            "order_id": self.order.id,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
            "category": "discount",
            "classification": "requires_review",
            "risk_level": "high",
            "risk_score": 75,
        }
        vals.update(values)
        return self.env["pos.risk.case"].create(vals)

    def test_case_gets_sequence_and_follows_workflow(self):
        case = self._case()
        self.assertTrue(case.name.startswith("RISK/"))
        case = case.with_user(self.manager)
        case.action_start_review()
        self.assertEqual(case.state, "under_review")
        case.write({"review_outcome": "false_positive"})
        case.action_resolve()
        self.assertEqual(case.state, "resolved")
        case.action_close()
        self.assertEqual(case.state, "closed")
        self.assertEqual(case.reviewed_by, self.manager)

    def test_invalid_transition_is_rejected(self):
        case = self._case(fingerprint="invalid-transition")
        with self.assertRaises(UserError):
            case.with_user(self.manager).action_resolve()

    def test_required_review_notes_are_enforced(self):
        case = self._case(fingerprint="required-notes")
        with self.assertRaises(ValidationError):
            case.write({"review_outcome": "cashier_mistake"})
