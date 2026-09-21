// Copyright (c) 2026, Smart Chem and contributors
// For license information, please see license.txt

frappe.ui.form.on("Indent", {
	setup: function (frm) {
		// port_of_loading / destination / origin / packing / lead_time all
		// share the one manager-editable "Indent Trade Term" master list
		// (see setup_indent_masters in install.py) -- each field is just
		// scoped to its own term_type so the same list backs all five.
		[
			["port_of_loading", "Port of Loading"],
			["destination", "Destination"],
			["origin", "Origin"],
			["packing", "Packing"],
			["lead_time", "Lead Time"],
		].forEach(([fieldname, term_type]) => {
			frm.set_query(fieldname, function () {
				return { filters: { term_type: term_type, is_disabled: 0 } };
			});
		});
	},

	refresh: function (frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("show_get_items_from_sales_invoice_button");
	},

	set_status_indicator: function (frm) {
		// Purely informational -- indent_status is entirely automatic (see
		// Indent.on_submit / close_indents_on_full_payment in utils.py),
		// there's nothing to click here. Blank pre-submission (the field
		// itself is hidden until then, see indent.json) falls through to
		// Frappe's own default Draft/Submitted/Cancelled indicator.
		const colors = { "In Process": "orange", Closed: "green" };
		if (frm.doc.indent_status) {
			frm.page.set_indicator(frm.doc.indent_status, colors[frm.doc.indent_status] || "gray");
		}
	},

	show_get_items_from_sales_invoice_button: function (frm) {
		// The reverse direction of the "Create > Indent" button on Sales
		// Invoice (SALES_INVOICE_CLIENT_SCRIPT_JS in install.py) -- lets
		// someone start from a blank Indent and pull an existing Sales
		// Invoice's data into it instead. Same direct data-fetch approach as
		// RFQ's "Get Items From > Quotation" button (inquiry.js): not
		// erpnext.utils.map_current_doc, which is built for picking rows
		// into an existing table, not cloning one whole source document.
		if (!frm.is_new() || !frappe.model.can_read("Sales Invoice")) return;

		frm.add_custom_button(
			__("Sales Invoice"),
			function () {
				frappe.prompt(
					[
						{
							fieldname: "sales_invoice",
							label: __("Sales Invoice"),
							fieldtype: "Link",
							options: "Sales Invoice",
							reqd: 1,
							get_query: function () {
								return {
									query: "smart_app.smart_app.doctype.indent.indent.get_sales_invoices_for_indent",
								};
							},
						},
					],
					function (values) {
						frappe.call({
							method: "smart_app.smart_app.doctype.indent.indent.get_indent_data_from_sales_invoice",
							args: { sales_invoice_name: values.sales_invoice },
							freeze: true,
							freeze_message: __("Fetching items..."),
							callback: function (r) {
								if (!r.message) return;
								const data = r.message;

								frm.set_value("company", data.company);
								frm.set_value("currency", data.currency);
								frm.set_value("sales_invoice", data.sales_invoice);
								frm.set_value("sales_order", data.sales_order);
								frm.set_value("inquiry", data.inquiry);
								frm.set_value("customer", data.customer);
								frm.set_value("customer_address_display", data.customer_address_display);
								frm.set_value("tc_name", data.tc_name);
								frm.set_value("terms", data.terms);

								frm.clear_table("items");
								(data.items || []).forEach(function (row) {
									frm.add_child("items", row);
								});

								frm.refresh_fields();
								frm.dirty();
							},
						});
					},
					__("Get Items From Sales Invoice"),
					__("Fetch")
				);
			},
			__("Get Items From"),
			"btn-default"
		);
	},
});
