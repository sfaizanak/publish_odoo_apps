/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { TextInputPopup } from "@point_of_sale/app/components/popups/text_input_popup/text_input_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

function makeEventUuid() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return "risk-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}

function monitoringEnabled(order) {
    return Boolean(order?.config_id?.pos_risk_monitoring_enabled);
}

patch(PosOrder.prototype, {
    initState() {
        super.initState(...arguments);
        this.uiState.risk_events ||= [];
    },

    _riskAddEvent(eventType, line, values = {}) {
        if (!monitoringEnabled(this)) {
            return;
        }
        this.uiState.risk_events.push({
            event_uuid: makeEventUuid(),
            order_uuid: this.uuid,
            order_line_uuid: line?.uuid,
            event_type: eventType,
            old_numeric_value: Number.isFinite(values.old_numeric_value) ? values.old_numeric_value : 0,
            new_numeric_value: Number.isFinite(values.new_numeric_value) ? values.new_numeric_value : 0,
            quantity: Number.isFinite(line?.qty) ? line.qty : 0,
            event_at: new Date().toISOString(),
            reason: values.reason || "",
        });
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(...arguments);
        if (monitoringEnabled(this) && this.uiState.risk_events?.length) {
            data.risk_event_payload = this.uiState.risk_events;
        }
        return data;
    },

    removeOrderline(line) {
        if (monitoringEnabled(this)) {
            for (const lineToRemove of line.getAllLinesInCombo()) {
                this._riskAddEvent("line_deleted", lineToRemove, {
                    old_numeric_value: lineToRemove.price_unit,
                    new_numeric_value: 0,
                });
            }
        }
        return super.removeOrderline(...arguments);
    },
});

patch(PosOrderline.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.risk_original_unit_price =
            typeof vals?.risk_original_unit_price === "number"
                ? vals.risk_original_unit_price
                : this.price_unit;
        this.risk_manual_price_change_count = vals?.risk_manual_price_change_count || 0;
    },

    setUnitPrice(price) {
        const previousPrice = this.price_unit;
        const manual = this.price_type === "manual";
        const result = super.setUnitPrice(...arguments);
        if (
            manual &&
            this.order_id &&
            this.order_id._riskAddEvent &&
            typeof previousPrice === "number" &&
            previousPrice !== this.price_unit
        ) {
            this.order_id._riskAddEvent("price_overridden", this, {
                old_numeric_value: previousPrice,
                new_numeric_value: this.price_unit,
            });
        }
        return result;
    },
});

patch(OrderSummary.prototype, {
    async setLinePrice(line, price) {
        let reason = "";
        if (
            monitoringEnabled(line.order_id) &&
            line.order_id.config_id.pos_risk_require_price_change_reason
        ) {
            reason = await makeAwaitable(this.dialog, TextInputPopup, {
                title: "Reason for manual price change",
                placeholder: "Optional reason",
            });
            if (reason === undefined) {
                return;
            }
        }
        const result = await super.setLinePrice(...arguments);
        line.risk_price_override_reason = reason;
        const event = line.order_id.uiState.risk_events?.at(-1);
        if (event?.event_type === "price_overridden" && event.order_line_uuid === line.uuid) {
            event.reason = reason;
        }
        return result;
    },
});
