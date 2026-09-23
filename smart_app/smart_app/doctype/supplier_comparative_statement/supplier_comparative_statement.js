// Copyright (c) 2026, Smart Chem and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supplier Comparative Statement", {
	refresh: function (frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("show_get_items_from_rfq_button");
		frm.trigger("show_refresh_rates_button");
	},

	set_status_indicator: function (frm) {
		if (frm.doc.docstatus === 1) {
			frm.page.set_indicator(__("Completed"), "green");
		}
	},

	show_get_items_from_rfq_button: function (frm) {
		// The only supported way to populate a blank statement -- see
		// _build_comparative_statement_from_rfq (supplier_comparative_
		// statement.py). Same "your own submitted RFQs, unless you're a
		// Commercial Manager/System Manager" scoping every other picker in
		// this app uses.
		if (!frm.is_new() || !frappe.model.can_read("Request for Quotation")) return;

		frm.add_custom_button(
			__("Request for Quotation"),
			function () {
				frappe.prompt(
					[
						{
							fieldname: "request_for_quotation",
							label: __("Request for Quotation"),
							fieldtype: "Link",
							options: "Request for Quotation",
							reqd: 1,
							get_query: function () {
								return {
									query:
										"smart_app.smart_app.doctype.supplier_comparative_statement.supplier_comparative_statement.get_rfqs_for_comparative_statement",
								};
							},
						},
					],
					function (values) {
						frappe.call({
							method:
								"smart_app.smart_app.doctype.supplier_comparative_statement.supplier_comparative_statement.get_comparative_statement_data_from_rfq",
							args: { rfq_name: values.request_for_quotation },
							freeze: true,
							freeze_message: __("Fetching suppliers and rates..."),
							callback: function (r) {
								if (!r.message) return;
								const data = r.message;

								frm.set_value("company", data.company);
								frm.set_value("currency", data.currency);
								frm.set_value("request_for_quotation", data.request_for_quotation);
								frm.set_value("quotation", data.quotation);
								frm.set_value("inquiry", data.inquiry);

								frm.clear_table("rfq_suppliers");
								(data.rfq_suppliers || []).forEach(function (row) {
									frm.add_child("rfq_suppliers", row);
								});

								frm.clear_table("items");
								(data.items || []).forEach(function (row) {
									frm.add_child("items", row);
								});

								frm.refresh_fields();
								frm.dirty();
							},
						});
					},
					__("Get Items From Request for Quotation"),
					__("Fetch")
				);
			},
			__("Get Items From"),
			"btn-default"
		);
	},

	show_refresh_rates_button: function (frm) {
		// Pulls in (item, supplier, rate) combinations from any Supplier
		// Quotation submitted against this statement's RFQ since it was
		// first built -- doesn't touch a row already selected, so it's
		// safe to click again as more supplier replies come in.
		if (frm.is_new() || frm.doc.docstatus !== 0 || !frm.doc.request_for_quotation) return;

		frm.add_custom_button(__("Refresh Rates"), function () {
			frappe.call({
				method:
					"smart_app.smart_app.doctype.supplier_comparative_statement.supplier_comparative_statement.refresh_rates",
				args: { comparative_statement_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Refreshing rates..."),
				callback: function (r) {
					frm.reload_doc();
					if (r.message) {
						frappe.show_alert({
							message: __("{0} new rate(s) added.", [r.message]),
							indicator: "green",
						});
					} else {
						frappe.show_alert({ message: __("No new rates found."), indicator: "blue" });
					}
				},
			});
		});
	},
});
