// Copyright (c) 2026, WizardLabz and contributors
// For license information, please see license.txt

frappe.ui.form.on("RabbitMQ Event Bus Connection", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Please save the document first."));
				return;
			}
			frappe.call({
				method: "frappe_event_bus_rabbitmq.doctype.rabbitmq_event_bus_connection.rabbitmq_event_bus_connection.test_connection",
				args: { connection_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Connecting to RabbitMQ..."),
				callback: (r) => {
					const data = r.message || {};
					if (data.success) {
						frappe.show_alert({
							message: data.message || __("Connection successful."),
							indicator: "green",
						});
					} else {
						frappe.msgprint({
							title: __("Connection Failed"),
							message: data.error || __("Unknown error"),
							indicator: "red",
						});
					}
				},
			});
		});
	},
});
