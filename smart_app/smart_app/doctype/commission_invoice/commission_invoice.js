// Copyright (c) 2026, Smart Chem and contributors
// For license information, please see license.txt

frappe.ui.form.on("Commission Invoice", {
	refresh: function (frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("show_get_items_from_indent_button");
		frm.trigger("show_financial_buttons");
	},

	set_status_indicator: function (frm) {
		const colors = { Submitted: "orange", Received: "green", "Written Off": "gray" };
		if (frm.doc.commission_status) {
			frm.page.set_indicator(frm.doc.commission_status, colors[frm.doc.commission_status] || "gray");
		}
	},

	show_get_items_from_indent_button: function (frm) {
		// The reverse direction of the "Create > Commission Invoice" button
		// on Indent (indent.js) -- lets someone start from a blank
		// Commission Invoice and pull an existing Indent's data into it.
		if (!frm.is_new() || !frappe.model.can_read("Indent")) return;

		frm.add_custom_button(
			__("Indent"),
			function () {
				frappe.prompt(
					[
						{
							fieldname: "indent",
							label: __("Indent"),
							fieldtype: "Link",
							options: "Indent",
							reqd: 1,
							get_query: function () {
								return {
									query: "smart_app.smart_app.doctype.commission_invoice.commission_invoice.get_indents_for_commission_invoice",
								};
							},
						},
					],
					function (values) {
						frappe.call({
							method: "smart_app.smart_app.doctype.commission_invoice.commission_invoice.get_commission_invoice_data_from_indent",
							args: { indent_name: values.indent },
							freeze: true,
							callback: function (r) {
								if (!r.message) return;
								Object.keys(r.message).forEach((key) => frm.set_value(key, r.message[key]));
								frm.dirty();
							},
						});
					},
					__("Get Data From Indent"),
					__("Fetch")
				);
			},
			__("Get Items From"),
			"btn-default"
		);
	},

	show_financial_buttons: function (frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.sales_invoice) return;

		frm.add_custom_button(__("Sales Invoice"), function () {
			frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
		}, __("View"));

		if (flt(frm.doc.outstanding_amount) > 0) {
			// Same call ERPNext's own "Create > Payment" button on Sales
			// Invoice makes -- get_payment_entry does all the account/
			// party/currency resolution; this just opens the result.
			frm.add_custom_button(__("Payment"), function () {
				frappe.call({
					method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
					args: { dt: "Sales Invoice", dn: frm.doc.sales_invoice },
					freeze: true,
					callback: function (r) {
						if (!r.message) return;
						const doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					},
				});
			}, __("Create"));

			if (frm.doc.commission_status !== "Written Off") {
				frm.add_custom_button(__("Write Off & Close"), function () {
					frappe.prompt(
						[
							{
								fieldname: "reason",
								label: __("Reason"),
								fieldtype: "Small Text",
								reqd: 1,
							},
						],
						function (values) {
							frappe.confirm(
								__("Write off the remaining {0} {1} and close this Commission Invoice and its Indent?", [
									frm.doc.currency,
									frm.doc.outstanding_amount,
								]),
								function () {
									frappe.call({
										method: "smart_app.smart_app.doctype.commission_invoice.commission_invoice.write_off_and_close",
										args: { commission_invoice_name: frm.doc.name, reason: values.reason },
										freeze: true,
										freeze_message: __("Writing off..."),
										callback: function () {
											frm.reload_doc();
										},
									});
								}
							);
						},
						__("Write Off & Close"),
						__("Write Off")
					);
				}).addClass("btn-danger");
			}

			frm.add_custom_button(__("Send Reminder"), function () {
				frappe.call({
					method: "smart_app.smart_app.doctype.commission_invoice.commission_invoice.send_commission_reminder",
					args: { commission_invoice_name: frm.doc.name },
					freeze: true,
					callback: function (r) {
						if (r.message) {
							frappe.show_alert({ message: __("Reminder sent."), indicator: "green" });
						} else {
							frappe.msgprint(__("No email on file for this Supplier's default contact."));
						}
					},
				});
			});
		}
	},
});
