# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_risk_monitoring_enabled = fields.Boolean(
        string="Enable POS Risk Monitoring",
        default=False,
        help="When enabled, completed orders become eligible for later risk analysis.",
    )

    @api.model
    def _load_pos_data_fields(self, config):
        # ``pos.config`` inherits ``pos.load.mixin`` directly and the core
        # model does not provide a field list of its own.  Calling
        # ``super()`` therefore returns ``[]`` and omits fields that core
        # ``_load_pos_data_read`` expects, notably ``use_pricelist``.
        # Keep the POS configuration payload explicit and include the fields
        # consumed by the standard POS client and by this addon.
        return [
            "id", "name", "currency_id", "company_id", "journal_id",
            "invoice_journal_id", "use_pricelist", "pricelist_id",
            "available_pricelist_ids", "iface_tax_included",
            "iface_available_categ_ids", "iface_cashdrawer",
            "iface_electronic_scale", "iface_print_via_proxy",
            "iface_scan_via_proxy", "iface_big_scrollbars",
            "iface_group_by_categ", "iface_print_auto",
            "iface_print_skip_screen", "restrict_price_control",
            "is_margins_costs_accessible_to_every_user", "cash_control",
            "set_maximum_difference", "receipt_header", "receipt_footer",
            "basic_receipt", "proxy_ip", "active", "uuid",
            "iface_tipproduct", "tip_product_id", "fiscal_position_ids",
            "default_fiscal_position_id", "default_bill_ids", "use_presets",
            "default_preset_id", "available_preset_ids",
            "tax_regime_selection", "limit_categories", "module_pos_restaurant",
            "module_pos_avatax", "module_pos_discount", "module_pos_appointment",
            "is_posbox", "is_header_or_footer", "module_pos_hr",
            "amount_authorized_diff", "payment_method_ids",
            "company_has_template", "current_user_id", "other_devices",
            "rounding_method", "cash_rounding", "only_round_cash_method",
            "manual_discount", "ship_later", "warehouse_id", "route_id",
            "picking_policy", "auto_validate_terminal_payment",
            "trusted_config_ids", "access_token", "show_product_images",
            "show_category_images", "note_ids", "module_pos_sms",
            "is_closing_entry_by_product", "order_edit_tracking",
            "fallback_nomenclature_id", "epson_printer_ip", "use_fast_payment",
            "fast_payment_method_ids", "pos_risk_monitoring_enabled",
        ]
