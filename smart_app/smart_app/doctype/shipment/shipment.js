// Copyright (c) 2026, Smart Chem and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shipment", {
	setup: function (frm) {
		frm.set_query("logistic_officer", function () {
			return { query: "smart_app.smart_app.doctype.shipment.shipment.get_logistic_officers" };
		});
	},

	refresh: function (frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("show_assign_button");
	},

	set_status_indicator: function (frm) {
		const colors = {
			"Pending Assignment": "red",
			Assigned: "orange",
			"In Progress": "blue",
			Arrived: "yellow",
			Completed: "green",
		};
		if (frm.doc.shipment_status) {
			frm.page.set_indicator(frm.doc.shipment_status, colors[frm.doc.shipment_status] || "gray");
		}
	},

	show_assign_button: function (frm) {
		// Step 12, "Assignment of region wise shipments" -- a dedicated
		// one-click action for Logistic Manager, same shape as Inquiry's
		// own Assign/Reassign button for Commercial Officer: calls
		// assign_logistic_officer (explicit role check +
		// ignore_permissions=True server-side) instead of editing the
		// read-only region/logistic_officer fields directly and hunting
		// for a way to save.
		if (frm.is_new() || !frappe.user_roles.includes("Logistic Manager")) return;

		const label = frm.doc.logistic_officer ? __("Reassign") : __("Assign");
		frm.add_custom_button(label, function () {
			frappe.prompt(
				[
					{
						fieldname: "region",
						label: __("Region"),
						fieldtype: "Link",
						options: "Shipment Region",
						default: frm.doc.region,
						get_query: function () {
							return { filters: { is_disabled: 0 } };
						},
					},
					{
						fieldname: "logistic_officer",
						label: __("Logistic Officer"),
						fieldtype: "Link",
						options: "User",
						reqd: 1,
						default: frm.doc.logistic_officer,
						get_query: function () {
							return {
								query: "smart_app.smart_app.doctype.shipment.shipment.get_logistic_officers",
							};
						},
					},
				],
				function (values) {
					frappe.call({
						method: "smart_app.smart_app.doctype.shipment.shipment.assign_logistic_officer",
						args: {
							shipment_name: frm.doc.name,
							region: values.region,
							logistic_officer: values.logistic_officer,
						},
						freeze: true,
						freeze_message: __("Assigning..."),
						callback: function () {
							frm.reload_doc();
						},
					});
				},
				__("Assign Logistic Officer"),
				__("Assign")
			);
		}).addClass("btn-primary");
	},
});
