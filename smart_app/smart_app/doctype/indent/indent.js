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
		frm.trigger("show_get_items_from_quotation_button");
		frm.trigger("show_create_commission_invoice_button");
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

	show_get_items_from_quotation_button: function (frm) {
		// The reverse direction of the "Create > Indent" button on Quotation
		// (setup_quotation_integration, install.py) -- lets someone start
		// from a blank Indent and pull an existing Quotation's data into it
		// instead. Same direct data-fetch approach as RFQ's own "Get Items
		// From > Quotation" button (inquiry.js): not erpnext.utils.
		// map_current_doc, which is built for picking rows into an existing
		// table, not cloning one whole source document. Reuses Quotation's
		// own picker query (get_quotations_for_rfq, inquiry.py) -- same
		// "your own submitted Quotations, or all of them if you're a
		// Manager" scoping RFQ's identical button already relies on.
		if (!frm.is_new() || !frappe.model.can_read("Quotation")) return;

		frm.add_custom_button(
			__("Quotation"),
			function () {
				frappe.prompt(
					[
						{
							fieldname: "quotation",
							label: __("Quotation"),
							fieldtype: "Link",
							options: "Quotation",
							reqd: 1,
							get_query: function () {
								return {
									query: "smart_app.smart_app.doctype.inquiry.inquiry.get_quotations_for_rfq",
								};
							},
						},
					],
					function (values) {
						frappe.call({
							method: "smart_app.smart_app.doctype.indent.indent.get_indent_data_from_quotation",
							args: { quotation_name: values.quotation },
							freeze: true,
							freeze_message: __("Fetching items..."),
							callback: function (r) {
								if (!r.message) return;
								const data = r.message;

								frm.set_value("company", data.company);
								frm.set_value("currency", data.currency);
								frm.set_value("quotation", data.quotation);
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
					__("Get Items From Quotation"),
					__("Fetch")
				);
			},
			__("Get Items From"),
			"btn-default"
		);
	},

	show_create_commission_invoice_button: function (frm) {
		// Once an Indent is submitted, the deal is formalised -- a
		// Commission Invoice can be raised against it any time from here
		// (see create_commission_invoice_from_indent, commission_invoice.py).
		if (frm.doc.docstatus !== 1 || !frappe.model.can_create("Commission Invoice")) return;

		frm.add_custom_button(
			__("Commission Invoice"),
			function () {
				frappe.call({
					method: "smart_app.smart_app.doctype.commission_invoice.commission_invoice.create_commission_invoice_from_indent",
					args: { indent_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Preparing Commission Invoice..."),
					callback: function (r) {
						if (r.message) {
							frappe.set_route("Form", "Commission Invoice", r.message);
						}
					},
				});
			},
			__("Create")
		);
	},
});
